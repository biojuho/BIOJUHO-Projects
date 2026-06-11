#!/usr/bin/env node

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function readText(path) {
  return readFileSync(join(root, path), "utf-8");
}

function unique(items) {
  return Array.from(new Set(items));
}

function scriptNamesFromIndex(html) {
  return unique(Array.from(html.matchAll(/<script\b[^>]*\bsrc="\.\/([^"]+\.js)"/g))
    .map((match) => match[1])
    .filter((name) => !name.startsWith("vendor/")));
}

function lazyScriptNamesFromOpsLoader(text) {
  return unique(Array.from(text.matchAll(/"([^"]+\.js)"/g)).map((match) => match[1]));
}

function missingTerms(text, terms) {
  return terms.filter((term) => !text.includes(term));
}

const indexText = readText("index.html");
const opsRuntimeText = readText("ops-runtime-loader.js");
const architectureText = readText("docs/app-architecture.md");
const readmeText = readText("README.md");
const packageJson = JSON.parse(readText("package.json"));

const initialRuntimeScripts = scriptNamesFromIndex(indexText);
const lazyRuntimeScripts = lazyScriptNamesFromOpsLoader(opsRuntimeText);
const requiredArchitectureTerms = unique([
  ...initialRuntimeScripts,
  ...lazyRuntimeScripts,
  "OPS_RUNTIME_VIEW_GROUPS",
  "MODAL_ACTION_HANDLERS",
  "npm run check:docs",
]);
const missingArchitectureTerms = missingTerms(architectureText, requiredArchitectureTerms);
const missingReadmeTerms = missingTerms(readmeText, [
  "docs/app-architecture.md",
  "npm run check:docs",
]);

if (packageJson.scripts?.["check:docs"] !== "node scripts/check-doc-architecture.mjs") {
  console.error("[check-doc-architecture] package.json is missing the check:docs script.");
  process.exitCode = 1;
}

if (missingArchitectureTerms.length) {
  console.error("[check-doc-architecture] docs/app-architecture.md is missing:");
  for (const term of missingArchitectureTerms) console.error(`  - ${term}`);
  process.exitCode = 1;
}

if (missingReadmeTerms.length) {
  console.error("[check-doc-architecture] README.md is missing:");
  for (const term of missingReadmeTerms) console.error(`  - ${term}`);
  process.exitCode = 1;
}

if (!process.exitCode) {
  console.log("[check-doc-architecture] PASS", {
    initialRuntimeScripts: initialRuntimeScripts.length,
    lazyRuntimeScripts: lazyRuntimeScripts.length,
  });
}
