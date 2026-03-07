import fs from "node:fs";
import path from "node:path";

const DIST_ASSETS_DIR = path.resolve("dist", "assets");
const MAX_CHUNK_KB = Number(process.env.MAX_CHUNK_KB || 500);
const MAX_ENTRY_KB = Number(process.env.MAX_ENTRY_KB || 260);

if (!fs.existsSync(DIST_ASSETS_DIR)) {
  console.error("[bundle-check] dist/assets not found. Run build first.");
  process.exit(1);
}

const files = fs
  .readdirSync(DIST_ASSETS_DIR)
  .filter((file) => file.endsWith(".js"))
  .map((file) => {
    const fullPath = path.join(DIST_ASSETS_DIR, file);
    const sizeBytes = fs.statSync(fullPath).size;
    return {
      file,
      sizeBytes,
      sizeKB: Number((sizeBytes / 1024).toFixed(2)),
    };
  })
  .sort((a, b) => b.sizeBytes - a.sizeBytes);

if (files.length === 0) {
  console.error("[bundle-check] No JS assets found in dist/assets.");
  process.exit(1);
}

const oversizedChunks = files.filter((file) => file.sizeKB > MAX_CHUNK_KB);
const entryChunk = files.find((file) => /^index-.*\.js$/.test(file.file));
const entryTooLarge = entryChunk ? entryChunk.sizeKB > MAX_ENTRY_KB : false;

console.log("[bundle-check] JS bundle summary (KB):");
for (const file of files.slice(0, 15)) {
  console.log(`- ${file.file}: ${file.sizeKB}`);
}

if (oversizedChunks.length > 0 || entryTooLarge) {
  if (oversizedChunks.length > 0) {
    console.error(
      `[bundle-check] Found chunk(s) larger than ${MAX_CHUNK_KB}KB:`,
    );
    oversizedChunks.forEach((chunk) =>
      console.error(`  - ${chunk.file}: ${chunk.sizeKB}KB`),
    );
  }

  if (entryTooLarge && entryChunk) {
    console.error(
      `[bundle-check] Entry chunk too large (> ${MAX_ENTRY_KB}KB): ${entryChunk.file} (${entryChunk.sizeKB}KB)`,
    );
  }

  process.exit(1);
}

console.log(
  `[bundle-check] OK (max chunk <= ${MAX_CHUNK_KB}KB, entry <= ${MAX_ENTRY_KB}KB)`,
);
