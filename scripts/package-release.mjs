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
import { basename, dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = join(root, "dist", "release");
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
    sourceCommit: process.env.SOURCE_COMMIT || currentCommit(),
    files,
  };
}

function currentCommit() {
  try {
    return execFileSync("git", ["rev-parse", "--short", "HEAD"], {
      cwd: root,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "";
  }
}

function writeReleaseNotes(manifest) {
  const totalBytes = manifest.files.reduce((sum, file) => sum + file.bytes, 0);
  const lines = [
    "# JooPark Workspace Release",
    "",
    `- Version: ${manifest.version}`,
    `- Generated: ${manifest.generatedAt}`,
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
    "BASE_URL=http://127.0.0.1:5178 node scripts/smoke-chrome.mjs",
    "BASE_URL=http://127.0.0.1:5178 node scripts/smoke-interactions.mjs",
    "node scripts/smoke-release.mjs",
    "```",
    "",
    "Expected result: verification and smoke commands report `status` as `pass`; the smoke output should also have empty `consoleIssues` and `networkIssues`. `smoke-release.mjs` is the full packaged-release gate: it rebuilds `dist/release`, verifies the manifest, serves the package on a temporary local port, route-smokes the served package, and runs the click/input interaction smoke.",
    "",
  ];
  writeFileSync(join(outDir, "RELEASE.md"), lines.join("\n"), "utf-8");
}

rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });
for (const entry of sourceEntries) copyEntry(entry);
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
