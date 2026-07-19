#!/usr/bin/env node
// CSS 사용처 래칫 게이트: styles.css에 정의된 클래스 중 런타임 코퍼스에서
// 참조되지 않는 클래스가 '베이스라인보다 늘어나면' 실패한다.
// (기존 미사용은 베이스라인으로 허용하되 한 방향 증가를 차단 — 2026-07 stage3에서 도입)
// 베이스라인 갱신: node scripts/check-css-usage.mjs --write-baseline
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const baselinePath = join(root, "data", "css-usage-baseline.json");
const writeBaseline = process.argv.includes("--write-baseline");

// 동적 클래스 조립 패밀리(템플릿 리터럴 `x-${...}` 등) — 접두사 일치 시 사용으로 간주
const dynamicPrefixes = [
  "toast-", "portfolio-action-", "alert-", "db-source-", "db-freshness-", "cal-dot-",
  "mig-", "gantt-bar-", "priority-", "kanban-source-", "kanban-density-", "pipe-wbs-",
  "review-result-", "prio-", "pal-icon-", "sheet-action", "sheet-meta-", "kpi-",
  "is-", "has-", "todo-due", "toast-in", "toast-out",
];

const css = readFileSync(join(root, "styles.css"), "utf8");
// 셀렉터부(중괄호 앞)에서만 .class 토큰 추출
const definedClasses = new Set();
for (const match of css.matchAll(/(^|\})([^{}]+)\{/g)) {
  const selector = match[2];
  if (selector.includes("@")) continue;
  for (const cls of selector.matchAll(/\.([A-Za-z_][A-Za-z0-9_-]*)/g)) {
    definedClasses.add(cls[1]);
  }
}

const corpusFiles = [
  ...readdirSync(root).filter((name) => name.endsWith(".js")),
  "index.html",
  "pharma-cockpit.html",
];
const corpus = corpusFiles
  .map((name) => {
    try { return readFileSync(join(root, name), "utf8"); } catch (_) { return ""; }
  })
  .join("\n");

function isUsed(cls) {
  if (dynamicPrefixes.some((prefix) => cls.startsWith(prefix))) return true;
  return new RegExp(`(?<![A-Za-z0-9_-])${cls.replace(/[-]/g, "\\-")}(?![A-Za-z0-9_-])`).test(corpus);
}

const unused = [...definedClasses].filter((cls) => !isUsed(cls)).sort();

if (writeBaseline) {
  writeFileSync(baselinePath, `${JSON.stringify({ generatedFor: "check-css-usage ratchet", unused }, null, 2)}\n`);
  console.log(`baseline written: ${unused.length} known-unused classes`);
  process.exit(0);
}

let baseline = [];
try { baseline = JSON.parse(readFileSync(baselinePath, "utf8")).unused || []; } catch (_) {}
const baselineSet = new Set(baseline);
const newUnused = unused.filter((cls) => !baselineSet.has(cls));
const healed = baseline.filter((cls) => !unused.includes(cls));

if (newUnused.length > 0) {
  console.error(`check:css fail — 새 미사용 클래스 ${newUnused.length}개 (정의했으면 사용하거나 지우세요):`);
  for (const cls of newUnused.slice(0, 30)) console.error(`  .${cls}`);
  process.exit(1);
}
console.log(`check:css pass — 정의 ${definedClasses.size}개, 미사용 ${unused.length}개(전부 베이스라인 허용)${healed.length ? `, 베이스라인 축소 가능 ${healed.length}개` : ""}`);
