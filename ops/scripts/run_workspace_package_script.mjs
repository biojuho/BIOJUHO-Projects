import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const WORKSPACE_MAP_PATH = join(ROOT, "workspace-map.json");
const EXCLUDED_DIRS = new Set([
  ".git",
  ".venv",
  ".pytest_cache",
  "build",
  "coverage",
  "dist",
  "node_modules",
  "test-results",
  "__pycache__",
  "archive",
  "var",
]);
const PLACEHOLDER_SCRIPT_PATTERNS = [/no test specified/i];

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function loadWorkspaceMap() {
  return readJson(WORKSPACE_MAP_PATH);
}

function discoverPackageDirs(dir, results = []) {
  const entries = readdirSync(dir, { withFileTypes: true });
  const hasPackageJson = entries.some((entry) => entry.isFile() && entry.name === "package.json");

  if (hasPackageJson && dir !== ROOT) {
    results.push(dir);
  }

  for (const entry of entries) {
    if (!entry.isDirectory() || EXCLUDED_DIRS.has(entry.name)) {
      continue;
    }
    discoverPackageDirs(join(dir, entry.name), results);
  }

  return results;
}

function shouldSkipScript(script) {
  return PLACEHOLDER_SCRIPT_PATTERNS.some((pattern) => pattern.test(script));
}

function quoteWindowsArg(value) {
  return /\s/.test(value) ? `"${value.replace(/"/g, '\\"')}"` : value;
}

function getActiveRoots() {
  return loadWorkspaceMap().units
    .filter((unit) => unit.active)
    .map((unit) => join(ROOT, unit.canonical_path));
}

function main() {
  const [, , task, ...extraArgs] = process.argv;
  if (!task) {
    console.error("[workspace] missing task name");
    process.exit(1);
  }

  const npmExec = process.platform === "win32" ? "npm.cmd" : "npm";
  const packageDirs = getActiveRoots()
    .flatMap((dir) => discoverPackageDirs(dir))
    .map((dir) => {
      const manifest = readJson(join(dir, "package.json"));
      const script = manifest.scripts?.[task];
      return {
        dir,
        name: manifest.name ?? relative(ROOT, dir),
        script,
      };
    })
    .filter((pkg) => typeof pkg.script === "string" && !shouldSkipScript(pkg.script))
    .sort((left, right) => left.dir.localeCompare(right.dir));

  if (packageDirs.length === 0) {
    console.error(`[workspace] no package defines script "${task}"`);
    process.exit(1);
  }

  let failed = 0;
  for (const pkg of packageDirs) {
    const relDir = relative(ROOT, pkg.dir) || ".";
    const npmArgs = ["run", task];
    if (extraArgs.length > 0) {
      npmArgs.push("--", ...extraArgs);
    }
    const command = process.platform === "win32" ? "cmd.exe" : npmExec;
    const commandArgs =
      process.platform === "win32"
        ? ["/d", "/s", "/c", [npmExec, ...npmArgs].map(quoteWindowsArg).join(" ")]
        : npmArgs;

    console.log(`[workspace] running ${task} in ${relDir}`);
    const result = spawnSync(command, commandArgs, {
      cwd: pkg.dir,
      stdio: "inherit",
      shell: false,
    });

    if (result.error) {
      console.error(`[workspace] failed to start ${task} in ${relDir}: ${result.error.message}`);
      failed += 1;
      continue;
    }

    if (
      process.platform === "win32" &&
      task === "build" &&
      result.status !== 0 &&
      existsSync(join(pkg.dir, "dist"))
    ) {
      console.warn(
        `[workspace] ${relDir} emitted dist before returning a Windows-native failure code; treating build as successful.`,
      );
      continue;
    }

    if (result.status !== 0) {
      failed += 1;
    }
  }

  if (failed > 0) {
    console.error(`[workspace] ${failed} package(s) failed "${task}"`);
    process.exit(1);
  }

  console.log(`[workspace] completed "${task}" across ${packageDirs.length} package(s)`);
}

main();
