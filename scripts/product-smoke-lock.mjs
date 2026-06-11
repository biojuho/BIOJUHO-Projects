import { createHash, randomUUID } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const defaultWaitMs = 30 * 60 * 1000;
const defaultStaleMs = 60 * 60 * 1000;
const defaultPollMs = 1000;
const defaultProgressMs = 15000;

function sleep(ms) {
  return new Promise((resolveSleep) => setTimeout(resolveSleep, ms));
}

function positiveNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function productSmokeLockDir(root) {
  const normalizedRoot = resolve(root);
  const rootKey = createHash("sha256").update(normalizedRoot).digest("hex").slice(0, 16);
  return join(tmpdir(), `joopark-product-smoke-${rootKey}.lock`);
}

function readOwner(ownerPath) {
  try {
    return JSON.parse(readFileSync(ownerPath, "utf-8"));
  } catch {
    return {};
  }
}

function pidIsAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error && error.code === "EPERM";
  }
}

function productSmokeLockHeartbeatMs(owner, ownerStatMs = 0, lockStatMs = 0) {
  const heartbeatMs = Date.parse(owner?.heartbeatAt || owner?.acquiredAt || "");
  if (Number.isFinite(heartbeatMs)) return heartbeatMs;
  if (Number.isFinite(ownerStatMs) && ownerStatMs > 0) return ownerStatMs;
  if (Number.isFinite(lockStatMs) && lockStatMs > 0) return lockStatMs;
  return 0;
}

function lockIsStale(lockDir, ownerPath, staleMs) {
  const owner = readOwner(ownerPath);
  if (!pidIsAlive(Number(owner.pid))) return true;

  let ownerStatMs = 0;
  let lockStatMs = 0;
  try {
    ownerStatMs = statSync(ownerPath).mtimeMs;
  } catch {
    ownerStatMs = 0;
  }
  try {
    lockStatMs = statSync(lockDir).mtimeMs;
  } catch {
    lockStatMs = 0;
  }
  const heartbeatMs = productSmokeLockHeartbeatMs(owner, ownerStatMs, lockStatMs);
  return heartbeatMs <= 0 || Date.now() - heartbeatMs > staleMs;
}

function writeOwner(ownerPath, owner) {
  writeFileSync(ownerPath, `${JSON.stringify({ ...owner, heartbeatAt: new Date().toISOString() }, null, 2)}\n`);
}

export async function withProductSmokeLock({ root, label = "product-smoke", progress } = {}, callback) {
  if (process.env.PRODUCT_SMOKE_LOCK_DISABLE === "1") return callback();
  if (typeof callback !== "function") throw new TypeError("withProductSmokeLock requires a callback");

  const lockDir = productSmokeLockDir(root || process.cwd());
  const ownerPath = join(lockDir, "owner.json");
  const waitMs = positiveNumber(process.env.PRODUCT_SMOKE_LOCK_WAIT_MS, defaultWaitMs);
  const staleMs = positiveNumber(process.env.PRODUCT_SMOKE_LOCK_STALE_MS, defaultStaleMs);
  const pollMs = positiveNumber(process.env.PRODUCT_SMOKE_LOCK_POLL_MS, defaultPollMs);
  const progressMs = positiveNumber(process.env.PRODUCT_SMOKE_LOCK_PROGRESS_MS, defaultProgressMs);
  const owner = {
    id: randomUUID(),
    pid: process.pid,
    label,
    root: resolve(root || process.cwd()),
    acquiredAt: new Date().toISOString(),
  };
  const startedAt = Date.now();
  let nextProgressAt = startedAt;

  while (Date.now() - startedAt < waitMs) {
    try {
      mkdirSync(lockDir);
      writeOwner(ownerPath, owner);
      const heartbeat = setInterval(() => {
        try {
          if (existsSync(lockDir)) writeOwner(ownerPath, owner);
        } catch {
          // Best-effort heartbeat; stale detection still protects future runs.
        }
      }, Math.min(progressMs, 30000));
      try {
        if (typeof progress === "function") progress(`acquired product smoke lock ${lockDir}`);
        return await callback();
      } finally {
        clearInterval(heartbeat);
        try {
          rmSync(lockDir, { recursive: true, force: true });
          if (typeof progress === "function") progress(`released product smoke lock ${lockDir}`);
        } catch {
          if (typeof progress === "function") progress(`product smoke lock cleanup skipped for ${lockDir}`);
        }
      }
    } catch (error) {
      if (!error || error.code !== "EEXIST") throw error;
      if (lockIsStale(lockDir, ownerPath, staleMs)) {
        rmSync(lockDir, { recursive: true, force: true });
        continue;
      }
      if (Date.now() >= nextProgressAt) {
        const activeOwner = readOwner(ownerPath);
        if (typeof progress === "function") {
          progress(`waiting for product smoke lock held by pid ${activeOwner.pid || "unknown"} (${activeOwner.label || "unknown"})`);
        }
        nextProgressAt = Date.now() + progressMs;
      }
      await sleep(pollMs);
    }
  }

  const ownerInfo = readOwner(ownerPath);
  throw new Error(`Timed out waiting for product smoke lock held by pid ${ownerInfo.pid || "unknown"} (${ownerInfo.label || "unknown"})`);
}
