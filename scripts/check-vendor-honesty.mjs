#!/usr/bin/env node

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const licenses = readFileSync(join(root, "vendor", "LICENSES.md"), "utf8");
const index = readFileSync(join(root, "index.html"), "utf8");

function sriForFile(path) {
  const digest = createHash("sha256").update(readFileSync(path)).digest("base64");
  return `sha256-${digest}`;
}

function scriptTagFor(file) {
  const escaped = file.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = index.match(new RegExp(`<script\\b[^>]*\\bsrc=["']\\./${escaped}["'][^>]*></script>`, "i"));
  return match ? match[0] : "";
}

assert.equal(pkg.private, true, "package must stay private for vendored/no-publish runtime");
assert.equal(pkg.license, "UNLICENSED", "package license must not imply vendored OSS relicensing");
assert.deepEqual(pkg.dependencies || {}, {}, "runtime should not claim npm dependencies");
assert.deepEqual(pkg.devDependencies || {}, {}, "devDependencies should stay empty for no-install static app");
assert.equal(Array.isArray(pkg.vendoredDependencies), true, "vendoredDependencies must be listed");
assert.equal(pkg.vendoredDependencies.length, 3, "vendoredDependencies must match vendor files");

for (const dep of pkg.vendoredDependencies) {
  assert.ok(dep.name && dep.version && dep.license && dep.file && dep.source && dep.global && dep.integrity, `incomplete vendored dependency: ${dep.name || dep.file}`);
  const filePath = join(root, dep.file);
  assert.ok(existsSync(filePath), `${dep.file} missing`);
  assert.equal(dep.integrity, sriForFile(filePath), `${dep.file} integrity mismatch`);
  assert.ok(licenses.includes(basename(dep.file)), `${dep.file} missing from vendor/LICENSES.md`);
  assert.ok(licenses.includes(dep.version), `${dep.version} missing from vendor/LICENSES.md`);
  assert.ok(licenses.includes(dep.license), `${dep.license} missing from vendor/LICENSES.md`);
  const tag = scriptTagFor(dep.file);
  assert.ok(tag, `${dep.file} not loaded by index.html`);
  assert.ok(tag.includes(`integrity="${dep.integrity}"`), `${dep.file} integrity missing from index.html`);
  assert.ok(tag.includes('crossorigin="anonymous"'), `${dep.file} crossorigin missing from index.html`);
}

assert.ok(licenses.includes("원본 그대로(수정 없이) 로컬 동봉"), "vendor/LICENSES.md must state local unmodified vendoring");

console.log("PASS vendor/package honesty");
