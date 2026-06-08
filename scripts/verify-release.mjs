#!/usr/bin/env node

import { createHash } from "node:crypto";
import {
  existsSync,
  readFileSync,
  readdirSync,
  statSync,
} from "node:fs";
import { basename, dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const releaseDir = process.argv[2] ? resolve(root, process.argv[2]) : join(root, "dist", "release");
const manifestPath = join(releaseDir, "release-manifest.json");
const provenancePath = join(releaseDir, "release-provenance.json");
const packageLockDir = `${releaseDir}.packaging.lock`;
const packageLockTimeoutMs = Number(process.env.RELEASE_PACKAGE_LOCK_TIMEOUT_MS || 60000);
const expectedRuntimeFiles = [
  "404.html",
  "_headers",
  "_redirects",
  "README.md",
  "search-empty-state.js",
  "home-execution-view.js",
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
  "workspace-storage.js",
  "storage-status-view.js",
  "settings-view.js",
  "system-status-view.js",
  "backup-import-guards.js",
  "backup-import-ui.js",
  "release-status.js",
  "operations-copy-actions.js",
  "verify-workspace-summary.js",
  "dialog-shell.js",
  "project-picker.js",
  "global-search.js",
  "command-palette.js",
  "db-catalog.js",
  "review-handoff.js",
  "review-result-view.js",
  "review-execution-checklist.js",
  "review-issue-payload.js",
  "review-result-state.js",
  "review-result-draft-state.js",
  "review-creation-actions.js",
  "review-package-view.js",
  "review-artifact-view.js",
  "review-artifact-state.js",
  "review-copy-actions.js",
  "review-submission-copy.js",
  "review-recommendation-export.js",
  "pwa-runtime.js",
  "app.js",
  "sw.js",
  "data/adoption-candidates.json",
  "data/launch-execution-packet.json",
  "data/launch-readiness-refresh.json",
  "data/output-quality-audit.json",
  "data/pages-attestation-proof.json",
  "data/publish-dispatch-plan.json",
  "data/publish-evidence.json",
  "data/remote-workflow-file-check.json",
  "data/repos.json",
  "data/workflow-ui-install-plan.json",
  "favicon.svg",
  "icons/icon-192.svg",
  "icons/icon-512.svg",
  "index.html",
  "site.webmanifest",
  "social-preview.png",
  "social-preview.svg",
  "styles.css",
  "autoresearch-results/release-readiness-summary.json",
  "autoresearch-results/verify-workspace-summary.json",
  "vercel.json",
  "vendor/LICENSES.md",
  "vendor/fuse.min.js",
  "vendor/marked.umd.js",
  "vendor/purify.min.js",
];
const expectedDeploySupportFiles = ["404.html", "_headers", "_redirects", "vercel.json"];
const expectedRuntimeScriptOrder = [
  "vendor/fuse.min.js",
  "vendor/marked.umd.js",
  "vendor/purify.min.js",
  "search-empty-state.js",
  "home-execution-view.js",
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
  "workspace-storage.js",
  "storage-status-view.js",
  "settings-view.js",
  "system-status-view.js",
  "backup-import-guards.js",
  "backup-import-ui.js",
  "release-status.js",
  "operations-copy-actions.js",
  "verify-workspace-summary.js",
  "dialog-shell.js",
  "project-picker.js",
  "global-search.js",
  "command-palette.js",
  "db-catalog.js",
  "review-handoff.js",
  "review-result-view.js",
  "review-execution-checklist.js",
  "review-issue-payload.js",
  "review-result-state.js",
  "review-result-draft-state.js",
  "review-creation-actions.js",
  "review-package-view.js",
  "review-artifact-view.js",
  "review-artifact-state.js",
  "review-copy-actions.js",
  "review-submission-copy.js",
  "review-recommendation-export.js",
  "pwa-runtime.js",
  "app.js",
];
const metadataFiles = new Set(["RELEASE.md", "release-manifest.json", "release-provenance.json"]);
const provenanceStatementType = "https://in-toto.io/Statement/v1";
const provenancePredicateType = "https://slsa.dev/provenance/v1";
const provenanceBuildType = "https://biojuho.local/joopark/static-release/v1";
const provenanceBuilderId = "https://biojuho.local/joopark/local-release-packager";
const expectedProvenanceDependencies = [
  "source-tree",
  "index.html",
  "llm-wiki-view.js",
  "pwa-runtime.js",
  "app.js",
  "sw.js",
  "styles.css",
  "README.md",
  "data",
  "vendor",
];
const sourceParityFiles = expectedRuntimeFiles.filter((file) => ![
  "404.html",
  "_headers",
  "_redirects",
  "data/launch-execution-packet.json",
  "data/launch-readiness-refresh.json",
  "data/output-quality-audit.json",
  "data/pages-attestation-proof.json",
  "data/publish-dispatch-plan.json",
  "data/publish-evidence.json",
  "data/remote-workflow-file-check.json",
  "data/workflow-ui-install-plan.json",
  "autoresearch-results/release-readiness-summary.json",
  "index.html",
  "vercel.json",
].includes(file));

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function sleepSync(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function waitForPackageLock() {
  const started = Date.now();
  while (existsSync(packageLockDir)) {
    if (Date.now() - started > packageLockTimeoutMs) {
      throw new Error(`Timed out waiting for release package lock: ${relative(root, packageLockDir)}`);
    }
    sleepSync(100);
  }
}

function walkFiles(baseDir) {
  const files = [];
  function visit(path) {
    const stat = statSync(path);
    if (stat.isDirectory()) {
      for (const name of readdirSync(path).sort()) visit(join(path, name));
      return;
    }
    if (stat.isFile()) files.push(path);
  }
  visit(baseDir);
  return files;
}

function runtimeFiles() {
  return walkFiles(releaseDir)
    .filter((file) => !metadataFiles.has(basename(file)))
    .map((file) => {
      const rel = relative(releaseDir, file).replaceAll("\\", "/");
      return {
        path: rel,
        bytes: statSync(file).size,
        sha256: sha256(file),
      };
    });
}

function failResult(failures) {
  return {
    status: "fail",
    releaseDir: relative(root, releaseDir),
    failures,
  };
}

function assertManifestShape(manifest, failures) {
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    failures.push("manifest must be a JSON object");
    return;
  }
  if (manifest.name !== "JooPark Workspace") failures.push("manifest name mismatch");
  if (manifest.version !== "3.0.0") failures.push("manifest version mismatch");
  if (!manifest.generatedAt || Number.isNaN(Date.parse(manifest.generatedAt))) {
    failures.push("manifest generatedAt must be an ISO timestamp");
  }
  if (!manifest.sourceCommit || typeof manifest.sourceCommit !== "string") {
    failures.push("manifest sourceCommit is missing");
  }
  if (!manifest.source || typeof manifest.source !== "object" || Array.isArray(manifest.source)) {
    failures.push("manifest source metadata is missing");
  } else {
    if (manifest.source.commit !== manifest.sourceCommit) {
      failures.push("manifest source.commit must match sourceCommit");
    }
    if (!manifest.source.branch || typeof manifest.source.branch !== "string") {
      failures.push("manifest source.branch is missing");
    }
    if (typeof manifest.source.dirty !== "boolean") {
      failures.push("manifest source.dirty must be a boolean");
    }
    if (!Array.isArray(manifest.source.dirtyFiles)) {
      failures.push("manifest source.dirtyFiles must be an array");
    } else if (!manifest.source.dirtyFiles.every((file) => typeof file === "string" && file.length > 0)) {
      failures.push("manifest source.dirtyFiles must contain non-empty strings");
    } else if (manifest.source.dirty !== (manifest.source.dirtyFiles.length > 0)) {
      failures.push("manifest source.dirty must match source.dirtyFiles length");
    }
  }
  if (!Array.isArray(manifest.files) || manifest.files.length === 0) {
    failures.push("manifest files must be a non-empty array");
  }
}

function verifyDeploySupport(failures) {
  const missingSupport = expectedDeploySupportFiles.filter((file) => !existsSync(join(releaseDir, file)));
  if (missingSupport.length > 0) {
    for (const file of missingSupport) failures.push(`deploy support file missing: ${file}`);
    return;
  }

  const indexHtml = readFileSync(join(releaseDir, "index.html"), "utf-8");
  const notFoundHtml = readFileSync(join(releaseDir, "404.html"), "utf-8");
  if (notFoundHtml !== indexHtml) {
    failures.push("404.html must mirror index.html for GitHub Pages static fallback");
  }

  const redirects = readFileSync(join(releaseDir, "_redirects"), "utf-8");
  if (!redirects.includes("/* /index.html 200")) {
    failures.push("_redirects must rewrite unmatched direct paths to index.html");
  }

  const headers = readFileSync(join(releaseDir, "_headers"), "utf-8");
  for (const term of [
    "X-Content-Type-Options: nosniff",
    "X-Frame-Options: DENY",
    "Referrer-Policy: strict-origin-when-cross-origin",
    "Permissions-Policy: camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    "Cache-Control: public, max-age=31536000, immutable",
    "Cache-Control: no-cache",
  ]) {
    if (!headers.includes(term)) failures.push(`_headers missing ${term}`);
  }

  let vercel;
  try {
    vercel = JSON.parse(readFileSync(join(releaseDir, "vercel.json"), "utf-8"));
  } catch (error) {
    failures.push(`vercel.json is not valid JSON: ${error.message}`);
    return;
  }
  if (vercel.$schema !== "https://openapi.vercel.sh/vercel.json") {
    failures.push("vercel.json schema mismatch");
  }
  if (vercel.cleanUrls !== false) failures.push("vercel.json cleanUrls must be false");
  if (vercel.trailingSlash !== false) failures.push("vercel.json trailingSlash must be false");
  const headerPairs = Array.isArray(vercel.headers)
    ? vercel.headers.flatMap((rule) => Array.isArray(rule.headers) ? rule.headers : [])
    : [];
  for (const pair of [
    ["X-Content-Type-Options", "nosniff"],
    ["X-Frame-Options", "DENY"],
    ["Referrer-Policy", "strict-origin-when-cross-origin"],
    ["Permissions-Policy", "camera=(), microphone=(), geolocation=()"],
    ["Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"],
    ["Cache-Control", "public, max-age=31536000, immutable"],
    ["Cache-Control", "no-cache"],
  ]) {
    if (!headerPairs.some((item) => item.key === pair[0] && item.value === pair[1])) {
      failures.push(`vercel.json missing ${pair[0]}=${pair[1]}`);
    }
  }
}

function duplicateHtmlIds(html) {
  const seen = new Set();
  const duplicates = new Set();
  for (const match of html.matchAll(/\bid\s*=\s*(["'])(.*?)\1/g)) {
    const id = match[2];
    if (seen.has(id)) duplicates.add(id);
    else seen.add(id);
  }
  return [...duplicates].sort();
}

function verifyUniqueHtmlIds(failures) {
  const indexPath = join(releaseDir, "index.html");
  if (!existsSync(indexPath)) return;
  const duplicates = duplicateHtmlIds(readFileSync(indexPath, "utf-8"));
  if (duplicates.length > 0) {
    failures.push(`index.html contains duplicate id values: ${duplicates.join(", ")}`);
  }
}

function htmlScriptSources(html) {
  return [...html.matchAll(/<script\b[^>]*\bsrc\s*=\s*(["'])(.*?)\1[^>]*>/gi)]
    .map((match) => match[2].replace(/^\.\//, "").replace(/[?#].*$/, ""));
}

function verifyRuntimeScriptOrder(failures) {
  const indexPath = join(releaseDir, "index.html");
  if (!existsSync(indexPath)) return;
  const scripts = htmlScriptSources(readFileSync(indexPath, "utf-8"));
  let previousIndex = -1;
  let previousScript = "";
  for (const script of expectedRuntimeScriptOrder) {
    const index = scripts.indexOf(script);
    if (index < 0) {
      failures.push(`index.html missing runtime script: ${script}`);
      continue;
    }
    if (index <= previousIndex) {
      failures.push(`index.html runtime script order is invalid: ${script} must load after ${previousScript}`);
    }
    previousIndex = index;
    previousScript = script;
  }
}

function pngInfo(path) {
  const buffer = readFileSync(path);
  if (buffer.length < 24 || buffer.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a") {
    return null;
  }
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20),
    bytes: buffer.length,
  };
}

function verifyPublicPreviewAssets(failures) {
  const indexPath = join(releaseDir, "index.html");
  const manifestFilePath = join(releaseDir, "site.webmanifest");
  const previewPath = join(releaseDir, "social-preview.png");
  if (!existsSync(indexPath) || !existsSync(manifestFilePath) || !existsSync(previewPath)) return;

  const info = pngInfo(previewPath);
  if (!info) {
    failures.push("social-preview.png must be a valid PNG file");
  } else {
    if (info.width !== 1200 || info.height !== 630) {
      failures.push(`social-preview.png must be 1200x630, got ${info.width}x${info.height}`);
    }
    if (info.bytes < 20_000) {
      failures.push("social-preview.png is unexpectedly small for a real app screenshot");
    }
  }

  const indexHtml = readFileSync(indexPath, "utf-8");
  for (const term of [
    "og:image\" content=\"./social-preview.png\"",
    "og:image:type\" content=\"image/png\"",
    "og:image:width\" content=\"1200\"",
    "og:image:height\" content=\"630\"",
    "twitter:image\" content=\"./social-preview.png\"",
  ]) {
    if (!indexHtml.includes(term)) failures.push(`index.html missing preview metadata: ${term}`);
  }

  let webManifest;
  try {
    webManifest = JSON.parse(readFileSync(manifestFilePath, "utf-8"));
  } catch (error) {
    failures.push(`site.webmanifest is not valid JSON: ${error.message}`);
    return;
  }
  const screenshots = Array.isArray(webManifest.screenshots) ? webManifest.screenshots : [];
  const previewScreenshot = screenshots.find((item) => item?.src === "./social-preview.png");
  if (!previewScreenshot) {
    failures.push("site.webmanifest screenshots must include ./social-preview.png");
  } else {
    if (previewScreenshot.sizes !== "1200x630") failures.push("site.webmanifest social preview screenshot size mismatch");
    if (previewScreenshot.type !== "image/png") failures.push("site.webmanifest social preview screenshot type mismatch");
    if (previewScreenshot.form_factor !== "wide") failures.push("site.webmanifest social preview screenshot form_factor must be wide");
  }
}

function verifyOfflineServiceWorker(failures) {
  const indexPath = join(releaseDir, "index.html");
  const appPath = join(releaseDir, "app.js");
  const pwaRuntimePath = join(releaseDir, "pwa-runtime.js");
  const serviceWorkerPath = join(releaseDir, "sw.js");
  if (!existsSync(indexPath) || !existsSync(appPath) || !existsSync(pwaRuntimePath) || !existsSync(serviceWorkerPath)) return;

  const appText = readFileSync(appPath, "utf-8");
  const pwaRuntimeText = readFileSync(pwaRuntimePath, "utf-8");
  const serviceWorkerText = readFileSync(serviceWorkerPath, "utf-8");
  for (const term of [
    "function registerServiceWorker",
    "pwaRuntimeCall(\"register\"",
    "refreshPwaRuntimeStatus({ render: true })",
  ]) {
    if (!appText.includes(term)) failures.push(`app.js missing service worker registration term: ${term}`);
  }
  for (const term of [
    "function secureEnoughForServiceWorker",
    "rootWindow.isSecureContext",
    "rootNavigator.serviceWorker.register(\"./sw.js\", { scope: \"./\" })",
  ]) {
    if (!pwaRuntimeText.includes(term)) failures.push(`pwa-runtime.js missing service worker registration term: ${term}`);
  }
  for (const term of [
    "CACHE_VERSION",
    "APP_SHELL_ASSETS",
    "OPTIONAL_APP_SHELL_ASSETS",
    "cache.addAll(APP_SHELL_ASSETS)",
    "./release-provenance.json",
    "function networkFirst",
    "self.skipWaiting()",
    "self.clients.claim()",
    "./index.html",
    "./styles.css",
    "./llm-wiki-view.js",
    "./home-execution-view.js",
    "./verify-workspace-summary.js",
    "./review-execution-checklist.js",
    "./review-issue-payload.js",
    "./review-result-state.js",
    "./review-result-draft-state.js",
    "./review-creation-actions.js",
    "./review-artifact-state.js",
    "./pwa-runtime.js",
    "./app.js",
    "./data/launch-readiness-refresh.json",
    "./data/output-quality-audit.json",
    "./data/pages-attestation-proof.json",
    "./autoresearch-results/verify-workspace-summary.json",
  ]) {
    if (!serviceWorkerText.includes(term)) failures.push(`sw.js missing offline shell term: ${term}`);
  }
}

function verifySourceParity(failures) {
  for (const path of sourceParityFiles) {
    const sourcePath = join(root, path);
    const releasePath = join(releaseDir, path);
    if (!existsSync(sourcePath)) {
      failures.push(`source parity file missing from source: ${path}`);
      continue;
    }
    if (!existsSync(releasePath)) {
      failures.push(`source parity file missing from release: ${path}`);
      continue;
    }
    const sourceBytes = statSync(sourcePath).size;
    const releaseBytes = statSync(releasePath).size;
    if (sourceBytes !== releaseBytes) {
      failures.push(`source parity byte mismatch for ${path}: source=${sourceBytes} release=${releaseBytes}`);
      continue;
    }
    if (sha256(sourcePath) !== sha256(releasePath)) {
      failures.push(`source parity sha256 mismatch for ${path}`);
    }
  }
}

function verifyReleaseProvenance(manifest, failures) {
  let provenance;
  try {
    provenance = JSON.parse(readFileSync(provenancePath, "utf-8"));
  } catch (error) {
    failures.push(`release-provenance.json is not valid JSON: ${error.message}`);
    return {
      subjectCount: 0,
      resolvedDependencyCount: 0,
      signed: null,
    };
  }

  if (!provenance || typeof provenance !== "object" || Array.isArray(provenance)) {
    failures.push("release-provenance.json must be a JSON object");
    return {
      subjectCount: 0,
      resolvedDependencyCount: 0,
      signed: null,
    };
  }

  if (provenance._type !== provenanceStatementType) {
    failures.push("provenance statement type mismatch");
  }
  if (provenance.predicateType !== provenancePredicateType) {
    failures.push("provenance predicateType mismatch");
  }

  const subjects = Array.isArray(provenance.subject) ? provenance.subject : [];
  if (!Array.isArray(provenance.subject) || subjects.length === 0) {
    failures.push("provenance subject must be a non-empty array");
  }
  const manifestSubject = subjects.find((item) => item?.name === "release-manifest.json");
  if (!manifestSubject) {
    failures.push("provenance subject missing release-manifest.json");
  } else if (manifestSubject.digest?.sha256 !== sha256(manifestPath)) {
    failures.push("provenance manifest subject sha256 mismatch");
  }

  const predicate = provenance.predicate;
  if (!predicate || typeof predicate !== "object" || Array.isArray(predicate)) {
    failures.push("provenance predicate must be a JSON object");
    return {
      subjectCount: subjects.length,
      resolvedDependencyCount: 0,
      signed: null,
    };
  }

  const buildDefinition = predicate.buildDefinition;
  const runDetails = predicate.runDetails;
  if (!buildDefinition || typeof buildDefinition !== "object" || Array.isArray(buildDefinition)) {
    failures.push("provenance buildDefinition is missing");
  }
  if (!runDetails || typeof runDetails !== "object" || Array.isArray(runDetails)) {
    failures.push("provenance runDetails is missing");
  }

  const externalParameters = buildDefinition?.externalParameters || {};
  if (buildDefinition?.buildType !== provenanceBuildType) {
    failures.push("provenance buildType mismatch");
  }
  if (externalParameters.sourceCommit !== manifest.sourceCommit) {
    failures.push("provenance externalParameters.sourceCommit must match manifest sourceCommit");
  }
  if (externalParameters.sourceBranch !== manifest.source.branch) {
    failures.push("provenance externalParameters.sourceBranch must match manifest source.branch");
  }
  if (externalParameters.sourceDirty !== manifest.source.dirty) {
    failures.push("provenance externalParameters.sourceDirty must match manifest source.dirty");
  }
  if (JSON.stringify(externalParameters.sourceDirtyFiles || []) !== JSON.stringify(manifest.source.dirtyFiles || [])) {
    failures.push("provenance externalParameters.sourceDirtyFiles must match manifest source.dirtyFiles");
  }

  const totalBytes = manifest.files.reduce((sum, file) => sum + file.bytes, 0);
  const internalParameters = buildDefinition?.internalParameters || {};
  if (internalParameters.packageScript !== "scripts/package-release.mjs") {
    failures.push("provenance internalParameters.packageScript mismatch");
  }
  if (internalParameters.manifestPath !== "release-manifest.json") {
    failures.push("provenance internalParameters.manifestPath mismatch");
  }
  if (internalParameters.provenancePath !== "release-provenance.json") {
    failures.push("provenance internalParameters.provenancePath mismatch");
  }
  if (internalParameters.runtimeFileCount !== manifest.files.length) {
    failures.push("provenance internalParameters.runtimeFileCount must match manifest file count");
  }
  if (internalParameters.totalBytes !== totalBytes) {
    failures.push("provenance internalParameters.totalBytes must match manifest total bytes");
  }

  const resolvedDependencies = Array.isArray(buildDefinition?.resolvedDependencies)
    ? buildDefinition.resolvedDependencies
    : [];
  if (!Array.isArray(buildDefinition?.resolvedDependencies) || resolvedDependencies.length === 0) {
    failures.push("provenance resolvedDependencies must be a non-empty array");
  }
  const dependencyNames = new Set(resolvedDependencies.map((item) => item?.name).filter(Boolean));
  for (const name of expectedProvenanceDependencies) {
    if (!dependencyNames.has(name)) failures.push(`provenance resolvedDependencies missing ${name}`);
  }
  for (const dependency of resolvedDependencies) {
    if (!dependency?.name) continue;
    const digest = dependency.digest || {};
    if (!digest.sha256 && !digest.gitCommit) {
      failures.push(`provenance dependency missing digest: ${dependency.name}`);
    }
  }

  const builder = runDetails?.builder || {};
  const metadata = runDetails?.metadata || {};
  if (builder.id !== provenanceBuilderId) {
    failures.push("provenance builder.id mismatch");
  }
  if (!metadata.invocationId || typeof metadata.invocationId !== "string") {
    failures.push("provenance metadata.invocationId is missing");
  }
  if (metadata.startedOn !== manifest.generatedAt) {
    failures.push("provenance metadata.startedOn must match manifest generatedAt");
  }
  if (!metadata.finishedOn || Number.isNaN(Date.parse(metadata.finishedOn))) {
    failures.push("provenance metadata.finishedOn must be an ISO timestamp");
  }

  const byproducts = Array.isArray(runDetails?.byproducts) ? runDetails.byproducts : [];
  const manifestByproduct = byproducts.find((item) => item?.name === "release-manifest.json");
  const releaseNotesByproduct = byproducts.find((item) => item?.name === "RELEASE.md");
  if (!manifestByproduct || manifestByproduct.digest?.sha256 !== sha256(manifestPath)) {
    failures.push("provenance byproducts must include release-manifest.json digest");
  }
  if (!releaseNotesByproduct || releaseNotesByproduct.digest?.sha256 !== sha256(join(releaseDir, "RELEASE.md"))) {
    failures.push("provenance byproducts must include RELEASE.md digest");
  }

  const jooparkRelease = predicate.joopark_release || {};
  if (jooparkRelease.signed !== false) {
    failures.push("provenance joopark_release.signed must be false until external attestation exists");
  }
  if (jooparkRelease.signatureStatus !== "unsigned-local-provenance") {
    failures.push("provenance joopark_release.signatureStatus mismatch");
  }
  if (jooparkRelease.manifestSubjectDigest !== sha256(manifestPath)) {
    failures.push("provenance joopark_release.manifestSubjectDigest must match manifest sha256");
  }
  if (jooparkRelease.runtimeFileCount !== manifest.files.length) {
    failures.push("provenance joopark_release.runtimeFileCount must match manifest file count");
  }
  if (jooparkRelease.totalBytes !== totalBytes) {
    failures.push("provenance joopark_release.totalBytes must match manifest total bytes");
  }

  return {
    subjectCount: subjects.length,
    resolvedDependencyCount: resolvedDependencies.length,
    signed: jooparkRelease.signed === true,
  };
}

function verify() {
  waitForPackageLock();
  const failures = [];
  if (!existsSync(releaseDir)) failures.push(`release directory missing: ${relative(root, releaseDir)}`);
  if (!existsSync(manifestPath)) failures.push("release-manifest.json missing");
  if (!existsSync(provenancePath)) failures.push("release-provenance.json missing");
  if (!existsSync(join(releaseDir, "RELEASE.md"))) failures.push("RELEASE.md missing");
  if (failures.length > 0) return failResult(failures);

  let manifest;
  try {
    manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  } catch (error) {
    return failResult([`release-manifest.json is not valid JSON: ${error.message}`]);
  }

  assertManifestShape(manifest, failures);
  if (failures.length > 0) return failResult(failures);

  const actual = runtimeFiles();
  const manifestFiles = manifest.files;
  const actualByPath = new Map(actual.map((file) => [file.path, file]));
  const manifestByPath = new Map();

  for (const file of manifestFiles) {
    if (!file || typeof file.path !== "string") {
      failures.push("manifest file entry missing path");
      continue;
    }
    if (file.path.startsWith("/") || file.path.includes("..")) {
      failures.push(`manifest file path is unsafe: ${file.path}`);
    }
    if (manifestByPath.has(file.path)) failures.push(`duplicate manifest file path: ${file.path}`);
    manifestByPath.set(file.path, file);
  }

  for (const expected of expectedRuntimeFiles) {
    if (!manifestByPath.has(expected)) failures.push(`required runtime file missing from manifest: ${expected}`);
    if (!actualByPath.has(expected)) failures.push(`required runtime file missing from release: ${expected}`);
  }

  for (const [path, actualFile] of actualByPath) {
    const manifestFile = manifestByPath.get(path);
    if (!manifestFile) {
      failures.push(`runtime file missing from manifest: ${path}`);
      continue;
    }
    if (manifestFile.bytes !== actualFile.bytes) {
      failures.push(`byte count mismatch for ${path}: manifest=${manifestFile.bytes} actual=${actualFile.bytes}`);
    }
    if (manifestFile.sha256 !== actualFile.sha256) {
      failures.push(`sha256 mismatch for ${path}`);
    }
  }

  for (const path of manifestByPath.keys()) {
    if (!actualByPath.has(path)) failures.push(`manifest file missing from release: ${path}`);
  }

  verifyDeploySupport(failures);
  verifyUniqueHtmlIds(failures);
  verifyRuntimeScriptOrder(failures);
  verifyPublicPreviewAssets(failures);
  verifyOfflineServiceWorker(failures);
  verifySourceParity(failures);
  const provenance = verifyReleaseProvenance(manifest, failures);

  if (failures.length > 0) return failResult(failures);
  return {
    status: "pass",
    releaseDir: relative(root, releaseDir),
    files: actual.length,
    bytes: actual.reduce((sum, file) => sum + file.bytes, 0),
    sourceCommit: manifest.sourceCommit,
    sourceDirty: manifest.source.dirty,
    sourceDirtyFiles: manifest.source.dirtyFiles.length,
    deploySupportFiles: expectedDeploySupportFiles.filter((file) => actualByPath.has(file)).length,
    sourceParityFiles: sourceParityFiles.length,
    provenanceSubjectCount: provenance.subjectCount,
    provenanceDependencyCount: provenance.resolvedDependencyCount,
    provenanceSigned: provenance.signed,
  };
}

const result = verify();
console.log(JSON.stringify(result, null, 2));
if (result.status !== "pass") process.exit(1);
