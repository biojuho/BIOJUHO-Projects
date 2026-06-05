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
  "404.html",
  "_headers",
  "_redirects",
  "README.md",
  "app.js",
  "data/adoption-candidates.json",
  "data/repos.json",
  "favicon.svg",
  "index.html",
  "styles.css",
  "vercel.json",
  "vendor/LICENSES.md",
  "vendor/fuse.min.js",
  "vendor/marked.umd.js",
  "vendor/purify.min.js",
];
const expectedDeploySupportFiles = ["404.html", "_headers", "_redirects", "vercel.json"];
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
  if (!manifest.source || typeof manifest.source !== "object" || Array.isArray(manifest.source)) {
    failures.push("manifest source metadata is missing");
  } else {
    if (manifest.source.commit !== manifest.sourceCommit) {
      failures.push("manifest source.commit must match sourceCommit");
    }
    if (!manifest.source.branch || typeof manifest.source.branch !== "string") {
      failures.push("manifest source.branch is missing");
    }
    if (typeof manifest.source.dirty !== "boolean") {
      failures.push("manifest source.dirty must be a boolean");
    }
    if (!Array.isArray(manifest.source.dirtyFiles)) {
      failures.push("manifest source.dirtyFiles must be an array");
    } else if (!manifest.source.dirtyFiles.every((file) => typeof file === "string" && file.length > 0)) {
      failures.push("manifest source.dirtyFiles must contain non-empty strings");
    } else if (manifest.source.dirty !== (manifest.source.dirtyFiles.length > 0)) {
      failures.push("manifest source.dirty must match source.dirtyFiles length");
    }
  }
  if (!Array.isArray(manifest.files) || manifest.files.length === 0) {
    failures.push("manifest files must be a non-empty array");
  }
}

function verifyDeploySupport(failures) {
  const missingSupport = expectedDeploySupportFiles.filter((file) => !existsSync(join(releaseDir, file)));
  if (missingSupport.length > 0) {
    for (const file of missingSupport) failures.push(`deploy support file missing: ${file}`);
    return;
  }

  const indexHtml = readFileSync(join(releaseDir, "index.html"), "utf-8");
  const notFoundHtml = readFileSync(join(releaseDir, "404.html"), "utf-8");
  if (notFoundHtml !== indexHtml) {
    failures.push("404.html must mirror index.html for GitHub Pages static fallback");
  }

  const redirects = readFileSync(join(releaseDir, "_redirects"), "utf-8");
  if (!redirects.includes("/* / 302")) {
    failures.push("_redirects must return unmatched direct paths to the app shell");
  }

  const headers = readFileSync(join(releaseDir, "_headers"), "utf-8");
  for (const term of [
    "X-Content-Type-Options: nosniff",
    "X-Frame-Options: DENY",
    "Referrer-Policy: strict-origin-when-cross-origin",
    "Permissions-Policy: camera=(), microphone=(), geolocation=()",
    "Cache-Control: public, max-age=31536000, immutable",
    "Cache-Control: no-cache",
  ]) {
    if (!headers.includes(term)) failures.push(`_headers missing ${term}`);
  }

  let vercel;
  try {
    vercel = JSON.parse(readFileSync(join(releaseDir, "vercel.json"), "utf-8"));
  } catch (error) {
    failures.push(`vercel.json is not valid JSON: ${error.message}`);
    return;
  }
  if (vercel.$schema !== "https://openapi.vercel.sh/vercel.json") {
    failures.push("vercel.json schema mismatch");
  }
  if (vercel.cleanUrls !== false) failures.push("vercel.json cleanUrls must be false");
  if (vercel.trailingSlash !== false) failures.push("vercel.json trailingSlash must be false");
  const headerPairs = Array.isArray(vercel.headers)
    ? vercel.headers.flatMap((rule) => Array.isArray(rule.headers) ? rule.headers : [])
    : [];
  for (const pair of [
    ["X-Content-Type-Options", "nosniff"],
    ["X-Frame-Options", "DENY"],
    ["Referrer-Policy", "strict-origin-when-cross-origin"],
    ["Permissions-Policy", "camera=(), microphone=(), geolocation=()"],
    ["Cache-Control", "public, max-age=31536000, immutable"],
    ["Cache-Control", "no-cache"],
  ]) {
    if (!headerPairs.some((item) => item.key === pair[0] && item.value === pair[1])) {
      failures.push(`vercel.json missing ${pair[0]}=${pair[1]}`);
    }
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

  verifyDeploySupport(failures);

  if (failures.length > 0) return failResult(failures);
  return {
    status: "pass",
    releaseDir: relative(root, releaseDir),
    files: actual.length,
    bytes: actual.reduce((sum, file) => sum + file.bytes, 0),
    sourceCommit: manifest.sourceCommit,
    sourceDirty: manifest.source.dirty,
    sourceDirtyFiles: manifest.source.dirtyFiles.length,
    deploySupportFiles: expectedDeploySupportFiles.filter((file) => actualByPath.has(file)).length,
  };
}

const result = verify();
console.log(JSON.stringify(result, null, 2));
if (result.status !== "pass") process.exit(1);
