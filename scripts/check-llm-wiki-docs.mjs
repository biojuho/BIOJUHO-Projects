#!/usr/bin/env node
// LLM 위키 문서 게이트 러너: scripts/check-llm-wiki-*.mjs 전부를 순차 실행한다.
// (기존에는 audit-release-readiness.mjs가 유일한 실행 소비자였으나, meta-machine 동결로
//  archive/meta-machine/으로 이관되면서 npm run check:wiki가 실행 경로가 됐다.)
import { execFileSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptsDir = dirname(fileURLToPath(import.meta.url));
const self = "check-llm-wiki-docs.mjs";
const checks = readdirSync(scriptsDir)
  .filter((name) => name.startsWith("check-llm-wiki-") && name.endsWith(".mjs") && name !== self)
  .sort();

if (checks.length === 0) {
  console.error("check:wiki fail — check-llm-wiki-*.mjs 게이트를 찾지 못했습니다");
  process.exit(1);
}

const failures = [];
for (const name of checks) {
  try {
    execFileSync(process.execPath, [join(scriptsDir, name)], { stdio: "pipe" });
  } catch (error) {
    const stderr = error.stderr ? error.stderr.toString().trim() : "";
    const stdout = error.stdout ? error.stdout.toString().trim() : "";
    failures.push(`${name}: ${stderr || stdout || error.message}`);
  }
}

if (failures.length > 0) {
  console.error(`check:wiki fail — ${failures.length}/${checks.length} 게이트 실패`);
  for (const failure of failures) console.error(`  - ${failure}`);
  process.exit(1);
}

console.log(`check:wiki pass — llm-wiki 문서 게이트 ${checks.length}개 통과`);
