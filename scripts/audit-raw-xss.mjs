#!/usr/bin/env node

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const runtimeFiles = [
  "app.js",
  "dialog-shell.js",
  "command-palette.js",
  "calendar-view.js",
  "todo-view.js",
  "notes-view.js",
  "habits-view.js",
  "stats-view.js",
  "llm-wiki-view.js",
  "portfolio-view.js",
  "kanban-view.js",
  "gantt-view.js",
  "team-view.js",
  "db-catalog.js",
  "release-status.js",
  "settings-view.js",
  "system-status-view.js",
  "dashboard-view.js",
  "storage-status-view.js",
  "home-execution-view.js",
  "review-result-view.js",
  "review-artifact-view.js",
  "review-package-view.js",
];

const forbiddenPatterns = [
  { label: "insertAdjacentHTML", pattern: /\binsertAdjacentHTML\s*\(/ },
  { label: "outerHTML assignment", pattern: /\.outerHTML\s*=/ },
  { label: "document.write", pattern: /\bdocument\.write\s*\(/ },
  { label: "eval", pattern: /\beval\s*\(/ },
  { label: "new Function", pattern: /\bnew\s+Function\s*\(/ },
  { label: "inline event handler attribute", pattern: /[\s'"`](?:onclick|ondblclick|onload|onerror|onchange|oninput|onsubmit|onreset|onfocus|onblur|onkeydown|onkeyup|onkeypress|onpointerdown|onpointermove|onpointerup|onpointercancel|onmousedown|onmouseup|onmousemove|onmouseover|onmouseout|onmouseenter|onmouseleave|ontouchstart|ontouchmove|ontouchend|ontouchcancel)\s*=/ },
  { label: "javascript URL", pattern: /javascript:/i },
];

const allowedInnerHtml = new Map([
  ["app.js", [/function setHTML\(node, htmlString\)/]],
  ["dialog-shell.js", [/function assignHTML\(node, htmlString\)/]],
  ["command-palette.js", [/results\.innerHTML = ""/, /results\.innerHTML = output/]],
]);

function read(relPath) {
  return readFileSync(join(root, relPath), "utf8");
}

function lineOf(source, index) {
  return source.slice(0, index).split(/\r?\n/).length;
}

function requireIncludes(file, source, terms, failures) {
  for (const term of terms) {
    if (!source.includes(term)) failures.push(`${file} missing XSS safety term: ${term}`);
  }
}

function auditForbidden(file, source, failures) {
  for (const rule of forbiddenPatterns) {
    const match = source.match(rule.pattern);
    if (match) failures.push(`${file}:${lineOf(source, match.index || 0)} forbidden ${rule.label}`);
  }
}

function auditInnerHtml(file, source, failures) {
  const allowed = allowedInnerHtml.get(file) || [];
  const regex = /\.innerHTML\s*=/g;
  let match;
  while ((match = regex.exec(source))) {
    const before = source.slice(Math.max(0, match.index - 160), Math.min(source.length, match.index + 120));
    if (!allowed.some((pattern) => pattern.test(before))) {
      failures.push(`${file}:${lineOf(source, match.index)} unreviewed innerHTML assignment`);
    }
  }
}

function auditRawContract(failures) {
  const app = read("app.js");
  requireIncludes("app.js", app, [
    "function escapeHtml(value)",
    ".replace(/&/g, \"&amp;\")",
    ".replace(/</g, \"&lt;\")",
    ".replace(/>/g, \"&gt;\")",
    "function raw(value)",
    "__raw: true",
    "function html(strings, ...values)",
    "if (v && v.__raw)",
    "return escapeHtml(item);",
    "DOMPurify.sanitize(rawHtml",
    "marked.parse(text",
  ], failures);
  const renderMarkdownBlock = app.slice(app.indexOf("function renderMarkdown"), app.indexOf("function debounce"));
  if (!/rawHtml\s*=\s*marked\.parse/.test(renderMarkdownBlock) || !/return DOMPurify\.sanitize\(rawHtml/.test(renderMarkdownBlock)) {
    failures.push("app.js renderMarkdown must sanitize marked output before returning");
  }
  const commandPalette = read("command-palette.js");
  requireIncludes("command-palette.js", commandPalette, [
    "output += paletteGroupHTML(currentGroup);",
    "return `<div class=\"pal-group\">${escape(group)}</div>`;",
    "output += `<span class=\"pal-label\">${escape(item.label)}</span>`;",
    "results.innerHTML = output;",
  ], failures);
}

const failures = [];
auditRawContract(failures);
for (const file of runtimeFiles) {
  const source = read(file);
  auditForbidden(file, source, failures);
  auditInnerHtml(file, source, failures);
}

const rawCallCount = runtimeFiles.reduce((count, file) => count + (read(file).match(/\braw\s*\(/g) || []).length, 0);
if (rawCallCount < 100) failures.push(`raw() audit expected broad runtime coverage, found only ${rawCallCount} calls`);

if (failures.length) {
  console.error("FAIL raw/XSS audit");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log(`PASS raw/XSS audit (${runtimeFiles.length} files, ${rawCallCount} raw calls reviewed)`);
