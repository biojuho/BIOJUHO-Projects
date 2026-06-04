#!/usr/bin/env node

import { createHash } from "node:crypto";
import {
  existsSync,
  readFileSync,
  readdirSync,
  statSync,
} from "node:fs";
import { basename, dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const releaseDir = process.argv[2] ? resolve(root, process.argv[2]) : join(root, "dist", "release");
const manifestPath = join(releaseDir, "release-manifest.json");
const expectedRuntimeFiles = [
  "README.md",
  "app.js",
  "data/adoption-candidates.json",
  "data/repos.json",
  "favicon.svg",
  "index.html",
  "styles.css",
  "vendor/LICENSES.md",
  "vendor/fuse.min.js",
  "vendor/marked.umd.js",
  "vendor/purify.min.js",
];
const metadataFiles = new Set(["RELEASE.md", "release-manifest.json"]);

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

function runtimeFiles() {
  return walkFiles(releaseDir)
    .filter((file) => !metadataFiles.has(basename(file)))
    .map((file) => {
      const rel = relative(releaseDir, file).replaceAll("\\", "/");
      return {
        path: rel,
        bytes: statSync(file).size,
        sha256: sha256(file),
      };
    });
}

function failResult(failures) {
  return {
    status: "fail",
    releaseDir: relative(root, releaseDir),
    failures,
  };
}

function assertManifestShape(manifest, failures) {
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    failures.push("manifest must be a JSON object");
    return;
  }
  if (manifest.name !== "JooPark Workspace") failures.push("manifest name mismatch");
  if (manifest.version !== "3.0.0") failures.push("manifest version mismatch");
  if (!manifest.generatedAt || Number.isNaN(Date.parse(manifest.generatedAt))) {
    failures.push("manifest generatedAt must be an ISO timestamp");
  }
  if (!manifest.sourceCommit || typeof manifest.sourceCommit !== "string") {
    failures.push("manifest sourceCommit is missing");
  }
  if (!Array.isArray(manifest.files) || manifest.files.length === 0) {
    failures.push("manifest files must be a non-empty array");
  }
}

function verify() {
  const failures = [];
  if (!existsSync(releaseDir)) failures.push(`release directory missing: ${relative(root, releaseDir)}`);
  if (!existsSync(manifestPath)) failures.push("release-manifest.json missing");
  if (!existsSync(join(releaseDir, "RELEASE.md"))) failures.push("RELEASE.md missing");
  if (failures.length > 0) return failResult(failures);

  let manifest;
  try {
    manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  } catch (error) {
    return failResult([`release-manifest.json is not valid JSON: ${error.message}`]);
  }

  assertManifestShape(manifest, failures);
  if (failures.length > 0) return failResult(failures);

  const actual = runtimeFiles();
  const manifestFiles = manifest.files;
  const actualByPath = new Map(actual.map((file) => [file.path, file]));
  const manifestByPath = new Map();

  for (const file of manifestFiles) {
    if (!file || typeof file.path !== "string") {
      failures.push("manifest file entry missing path");
      continue;
    }
    if (file.path.startsWith("/") || file.path.includes("..")) {
      failures.push(`manifest file path is unsafe: ${file.path}`);
    }
    if (manifestByPath.has(file.path)) failures.push(`duplicate manifest file path: ${file.path}`);
    manifestByPath.set(file.path, file);
  }

  for (const expected of expectedRuntimeFiles) {
    if (!manifestByPath.has(expected)) failures.push(`required runtime file missing from manifest: ${expected}`);
    if (!actualByPath.has(expected)) failures.push(`required runtime file missing from release: ${expected}`);
  }

  for (const [path, actualFile] of actualByPath) {
    const manifestFile = manifestByPath.get(path);
    if (!manifestFile) {
      failures.push(`runtime file missing from manifest: ${path}`);
      continue;
    }
    if (manifestFile.bytes !== actualFile.bytes) {
      failures.push(`byte count mismatch for ${path}: manifest=${manifestFile.bytes} actual=${actualFile.bytes}`);
    }
    if (manifestFile.sha256 !== actualFile.sha256) {
      failures.push(`sha256 mismatch for ${path}`);
    }
  }

  for (const path of manifestByPath.keys()) {
    if (!actualByPath.has(path)) failures.push(`manifest file missing from release: ${path}`);
  }

  if (failures.length > 0) return failResult(failures);
  return {
    status: "pass",
    releaseDir: relative(root, releaseDir),
    files: actual.length,
    bytes: actual.reduce((sum, file) => sum + file.bytes, 0),
    sourceCommit: manifest.sourceCommit,
  };
}

const result = verify();
console.log(JSON.stringify(result, null, 2));
if (result.status !== "pass") process.exit(1);
