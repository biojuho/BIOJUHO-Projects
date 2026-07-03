#!/usr/bin/env node

import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function readFile(relPath) {
  try {
    return readFileSync(join(root, relPath), "utf8");
  } catch {
    return "";
  }
}

const css = readFile("styles.css");
const html = readFile("index.html");
const appJs = readFile("app.js");

// ARIA/role/tabindex live in the JS view modules that render the DOM, not only in
// static index.html. Scan the full rendered-markup corpus (index.html + every
// top-level view/runtime .js) so the score reflects the actual accessible DOM
// instead of penalising patterns that are present but emitted dynamically.
const markup = [html, appJs]
  .concat(
    readdirSync(root)
      .filter((name) => name.endsWith(".js") && name !== "app.js")
      .map((name) => readFile(name)),
  )
  .join("\n");

let score = 0;
const checks = {};

function check(id, condition, points) {
  checks[id] = condition;
  if (condition) score += points;
}

check("prefers_reduced_motion", css.includes("prefers-reduced-motion"), 10);
check("aria_live_polite", markup.includes('aria-live="polite"') || markup.includes("aria-live"), 10);
check("aria_live_assertive", markup.includes('role="alert"') || markup.includes('aria-live="assertive"'), 5);
check("focus_visible", css.includes(":focus-visible") || css.includes("focus-visible"), 10);
check("skip_to_content", html.includes("skip") && html.includes("content"), 5);
check("semantic_nav", html.includes("<nav"), 5);
check("semantic_main", html.includes("<main"), 5);
check("semantic_header", html.includes("<header"), 3);
check("semantic_footer", html.includes("<footer"), 3);
check("aria_label_buttons", (markup.match(/aria-label/g) || []).length >= 5, 10);
check("role_dialog", markup.includes('role="dialog"'), 5);
check("role_status", markup.includes('role="status"'), 5);
check("role_listbox", markup.includes('role="listbox"'), 3);
check("role_combobox", markup.includes('role="combobox"'), 3);
check("aria_expanded", markup.includes("aria-expanded"), 5);
check("aria_pressed", markup.includes("aria-pressed"), 3);
check("aria_hidden", markup.includes('aria-hidden'), 3);
check("tabindex", markup.includes("tabindex"), 3);
check("lang_attribute", html.includes('lang='), 3);
check("meta_viewport", html.includes("viewport"), 2);
check("color_contrast_vars", css.includes("--bg") && css.includes("--text"), 5);
check("reduced_motion_transitions", css.includes("transition") && css.includes("prefers-reduced-motion"), 10);
check("scrollbar_styling", css.includes("scrollbar") || css.includes("::-webkit-scrollbar"), 2);
check("high_contrast_support", css.includes("forced-colors") || css.includes("prefers-contrast"), 5);

const maxScore = 100;
const normalizedScore = Math.min(100, Math.round((score / maxScore) * 100));

console.log(`accessibility_score=${normalizedScore}`);
console.log(JSON.stringify({ score: normalizedScore, rawScore: score, checks }, null, 2));
