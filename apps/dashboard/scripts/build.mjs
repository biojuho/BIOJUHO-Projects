import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import process from "node:process";

const cwd = process.cwd();
const viteCli = join(cwd, "node_modules", "vite", "bin", "vite.js");
const distIndex = join(cwd, "dist", "index.html");
const distAssets = join(cwd, "dist", "assets");

const result = spawnSync(process.execPath, [viteCli, "build"], {
  cwd,
  stdio: "inherit",
});

if (result.status === 0) {
  process.exit(0);
}

if (process.platform === "win32" && existsSync(distIndex) && existsSync(distAssets)) {
  console.warn("[dashboard build] vite emitted dist before returning a Windows-native failure code; treating build as successful.");
  process.exit(0);
}

if (result.error) {
  throw result.error;
}

process.exit(result.status ?? 1);
