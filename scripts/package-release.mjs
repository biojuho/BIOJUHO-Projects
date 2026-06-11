#!/usr/bin/env node

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  renameSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { basename, dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = process.env.RELEASE_OUT_DIR
  ? resolve(root, process.env.RELEASE_OUT_DIR)
  : join(root, "dist", "release");
let packageDir = outDir;
const packageLockDir = `${outDir}.packaging.lock`;
const packageLockTimeoutMs = positiveMsOption(process.env.RELEASE_PACKAGE_LOCK_TIMEOUT_MS, 60000);
const packageLockStaleMs = positiveMsOption(process.env.RELEASE_PACKAGE_LOCK_STALE_MS, 10 * 60 * 1000);

function positiveMsOption(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
  return parsed;
}

const sourceEntries = [
  "index.html",
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
  "keyboard-shortcuts.js",
  "interaction-setup.js",
  "event-reminders.js",
  "footer-clock.js",
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
  "runtime-error-boundary.js",
  "pwa-runtime.js",
  "workspace-seed-data.js",
  "home-view.js",
  "dashboard-view.js",
  "dashboard-insights-engine.js",
  "dashboard-prioritization.js",
  "dashboard-autoresearch-loop.js",
  "dashboard-evidence-receipts.js",
  "dashboard-storage.js",
  "ops-runtime-loader.js",
  "app.js",
  "sw.js",
  "styles.css",
  "favicon.svg",
  "icons",
  "site.webmanifest",
  "social-preview.png",
  "social-preview.svg",
  "README.md",
  "data",
  "vendor",

];
const generatedEvidenceEntries = [
  {
    path: "autoresearch-results/release-readiness-summary.json",
    create: createReleaseReadinessBootstrap,
  },
  {
    path: "autoresearch-results/verify-workspace-summary.json",
    create: createVerifyWorkspaceBootstrap,
  },
];
const runtimeAssets = [
  { path: "styles.css", attr: "href" },
  { path: "search-empty-state.js", attr: "src" },
  { path: "home-execution-view.js", attr: "src" },
  { path: "calendar-view.js", attr: "src" },
  { path: "todo-view.js", attr: "src" },
  { path: "notes-view.js", attr: "src" },
  { path: "habits-view.js", attr: "src" },
  { path: "stats-view.js", attr: "src" },
  { path: "llm-wiki-view.js", attr: "src" },
  { path: "portfolio-view.js", attr: "src" },
  { path: "kanban-view.js", attr: "src" },
  { path: "gantt-view.js", attr: "src" },
  { path: "team-view.js", attr: "src" },
  { path: "workspace-storage.js", attr: "src" },
  { path: "dashboard-storage.js", attr: "src" },
  { path: "dashboard-prioritization.js", attr: "src" },
  { path: "dashboard-evidence-receipts.js", attr: "src" },
  { path: "dashboard-insights-engine.js", attr: "src" },
  { path: "dashboard-autoresearch-loop.js", attr: "src" },
  { path: "dashboard-view.js", attr: "src" },
  { path: "storage-status-view.js", attr: "src" },
  { path: "settings-view.js", attr: "src" },
  { path: "system-status-view.js", attr: "src" },
  { path: "backup-import-guards.js", attr: "src" },
  { path: "backup-import-ui.js", attr: "src" },
  { path: "dialog-shell.js", attr: "src" },
  { path: "project-picker.js", attr: "src" },
  { path: "global-search.js", attr: "src" },
  { path: "command-palette.js", attr: "src" },
  { path: "keyboard-shortcuts.js", attr: "src" },
  { path: "interaction-setup.js", attr: "src" },
  { path: "event-reminders.js", attr: "src" },
  { path: "footer-clock.js", attr: "src" },
  { path: "db-catalog.js", attr: "src" },
  { path: "runtime-error-boundary.js", attr: "src" },
  { path: "pwa-runtime.js", attr: "src" },
  { path: "workspace-seed-data.js", attr: "src" },
  { path: "home-view.js", attr: "src" },
  { path: "ops-runtime-loader.js", attr: "src" },
  { path: "app.js", attr: "src" },

];
const releaseMetadataFiles = new Set(["RELEASE.md", "release-manifest.json", "release-provenance.json"]);
const provenanceStatementType = "https://in-toto.io/Statement/v1";
const provenancePredicateType = "https://slsa.dev/provenance/v1";
const provenanceBuildType = "https://biojuho.local/joopark/static-release/v1";
const provenanceBuilderId = "https://biojuho.local/joopark/local-release-packager";
const contentSecurityPolicyBase = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'";
const contentSecurityPolicyHeader = `${contentSecurityPolicyBase}; frame-ancestors 'none'`;

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
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

function sourceEntryResource(entry) {
  const source = join(root, entry);
  const stat = statSync(source);
  if (stat.isFile()) {
    return {
      name: entry,
      uri: `git+file://./${entry}`,
      digest: { sha256: sha256(source) },
    };
  }

  const hash = createHash("sha256");
  let fileCount = 0;
  for (const file of walkFiles(source)) {
    const rel = relative(root, file).replaceAll("\\", "/");
    hash.update(rel);
    hash.update("\0");
    hash.update(sha256(file));
    hash.update("\n");
    fileCount += 1;
  }
  return {
    name: entry,
    uri: `git+file://./${entry}`,
    digest: { sha256: hash.digest("hex") },
    annotations: {
      "joopark.fileCount": fileCount,
    },
  };
}

function copyEntry(entry) {
  const source = join(root, entry);
  const target = join(packageDir, entry);
  if (!existsSync(source)) throw new Error(`Missing release source: ${entry}`);
  const stat = statSync(source);
  if (stat.isDirectory()) {
    for (const file of walkFiles(source)) {
      const rel = relative(source, file);
      const dest = join(target, rel);
      mkdirSync(dirname(dest), { recursive: true });
      copyFileSync(file, dest);
    }
    return;
  }
  mkdirSync(dirname(target), { recursive: true });
  copyFileSync(source, target);
}

function copyOrGenerateEvidenceEntry(entry) {
  const source = join(root, entry.path);
  const target = join(packageDir, entry.path);
  mkdirSync(dirname(target), { recursive: true });
  if (existsSync(source)) {
    copyFileSync(source, target);
    return { path: entry.path, source: "source" };
  }
  writeFileSync(target, `${JSON.stringify(entry.create(), null, 2)}\n`, "utf-8");
  return { path: entry.path, source: "bootstrap" };
}

function createReleaseReadinessBootstrap() {
  const generatedAt = new Date().toISOString();
  return {
    schemaVersion: "joopark-release-readiness-summary/v1",
    generatedAt,
    sourceCommit: process.env.SOURCE_COMMIT || currentCommit(),
    command: "node scripts/audit-release-readiness.mjs --format=summary",
    status: "not_run",
    checks: {
      pass: 0,
      fail: 0,
      notRun: 1,
      blocked: 0,
      total: 1,
    },
    packagedBrowserGate: {
      status: "not_run",
      cached: false,
      cache: {
        status: "bootstrap",
        contextMatched: false,
        issues: ["release_readiness_summary_missing_from_source"],
        contextMismatches: [],
      },
    },
    packageBootstrap: {
      source: "scripts/package-release.mjs",
      reason: "release readiness summary source was missing in this checkout",
      repairCommand: "node scripts/audit-release-readiness.mjs --format=summary",
      validForExternalClaim: false,
    },
  };
}

function createVerifyWorkspaceBootstrap() {
  const generatedAt = new Date().toISOString();
  return {
    schemaVersion: "joopark-verify-workspace/v1",
    status: "fail",
    generatedAt,
    startedAt: generatedAt,
    durationMs: 0,
    command: "npm run verify:full",
    runner: "scripts/package-release.mjs",
    syncArtifacts: false,
    evidenceSyncRequired: true,
    evidenceSyncPass: false,
    stepResults: [],
    artifacts: {
      releaseReadiness: {
        path: "autoresearch-results/release-readiness-summary.json",
        status: "not_run",
        generatedAt: "",
        summary: "0 pass, 0 fail, 1 not_run, 0 blocked",
        checks: { pass: 0, fail: 0, notRun: 1, blocked: 0 },
      },
      launchReadiness: {
        path: "data/launch-readiness-refresh.json",
        status: "missing",
        generatedAt: "",
        latestGateSummary: "0 pass, 0 fail, 0 not_run, 0 blocked",
        safeToDispatch: false,
        readyForExternalClaim: false,
        workflowScopeInstallBlocked: false,
      },
      outputQuality: {
        path: "data/output-quality-audit.json",
        status: "missing",
        generatedAt: "",
        releaseQualityReady: false,
        publicLaunchProofReady: false,
        readyForExternalClaim: false,
        latestGateSummary: "0 pass, 0 fail, 0 not_run, 0 blocked",
      },
      productLoop: {
        path: "autoresearch-results/joopark-product-loop.json",
        status: "missing",
        generatedAt: "",
        latestGateSummary: "0 pass, 0 fail, 0 not_run, 0 blocked",
        latestExperiment: "",
      },
      evidenceSync: {
        status: "fail",
        productLoopGateParityReady: false,
        productLoopPublishParityReady: false,
        summarySyncReady: false,
        outputQualityGeneratedAt: "",
        productLoopSummarySyncOutputQualityGeneratedAt: "",
        source: "scripts/package-release.mjs",
        fullVerifyCommand: "npm run verify:full",
      },
    },
    packageBootstrap: {
      source: "scripts/package-release.mjs",
      reason: "verify workspace summary source was missing in this checkout",
      repairCommand: "npm run verify:full",
      validForExternalClaim: false,
    },
    externalClaimGuard: "Do not claim readyForExternalClaim until release quality, public launch proof, and external completion claim proof all pass.",
  };
}

function versionRuntimeAssetRefs() {
  const indexPath = join(packageDir, "index.html");
  let html = readFileSync(indexPath, "utf-8");
  for (const asset of runtimeAssets) {
    const assetPath = join(packageDir, asset.path);
    if (!existsSync(assetPath)) throw new Error(`Missing runtime asset for versioning: ${asset.path}`);
    const assetHash = sha256(join(packageDir, asset.path)).slice(0, 12);
    const escapedPath = asset.path.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const pattern = new RegExp(`(${asset.attr}=["'])\\./${escapedPath}(?:\\?v=[^"']*)?(["'])`, "g");
    let replacements = 0;
    html = html.replace(pattern, (_match, prefix, quote) => {
      replacements += 1;
      return `${prefix}./${asset.path}?v=${assetHash}${quote}`;
    });
    if (replacements === 0) throw new Error(`Runtime asset version ref missing in index.html: ${asset.path}`);
  }
  writeFileSync(indexPath, html, "utf-8");
}

function buildManifest() {
  const source = sourceMetadata();
  const files = walkFiles(packageDir)
    .filter((file) => !releaseMetadataFiles.has(basename(file)))
    .map((file) => {
      const rel = relative(packageDir, file).replaceAll("\\", "/");
      return {
        path: rel,
        bytes: statSync(file).size,
        sha256: sha256(file),
      };
    });
  return {
    name: "JooPark Workspace",
    version: "3.0.0",
    generatedAt: new Date().toISOString(),
    sourceCommit: source.commit,
    source,
    files,
  };
}

function gitOutput(args) {
  return gitOutputRaw(args).trim();
}

function gitOutputRaw(args) {
  try {
    return execFileSync("git", args, {
      cwd: root,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "ignore"],
    }).replace(/\r?\n$/, "");
  } catch {
    return "";
  }
}

function currentCommit() {
  return gitOutput(["rev-parse", "--short", "HEAD"]);
}

function sourceMetadata() {
  const statusText = gitOutputRaw(["status", "--short", "--untracked-files=all"]);
  const dirtyFiles = statusText ? statusText.split("\n").filter(Boolean) : [];
  return {
    commit: process.env.SOURCE_COMMIT || currentCommit(),
    branch: gitOutput(["branch", "--show-current"]) || gitOutput(["rev-parse", "--abbrev-ref", "HEAD"]),
    dirty: dirtyFiles.length > 0,
    dirtyFiles,
  };
}

function writeReleaseNotes(manifest) {
  const totalBytes = manifest.files.reduce((sum, file) => sum + file.bytes, 0);
  const dirtyLabel = manifest.source?.dirty ? `dirty (${manifest.source.dirtyFiles.length} paths)` : "clean";
  const lines = [
    "# JooPark Workspace Release",
    "",
    `- Version: ${manifest.version}`,
    `- Generated: ${manifest.generatedAt}`,
    `- Source commit: ${manifest.sourceCommit}`,
    `- Source branch: ${manifest.source?.branch || "unknown"}`,
    `- Source tree: ${dirtyLabel}`,
    `- Runtime files: ${manifest.files.length}`,
    `- Total bytes: ${totalBytes}`,
    "- Provenance: release-provenance.json (in-toto Statement v1 / SLSA provenance v1, unsigned-local-provenance)",
    "",
    "## Run",
    "",
    "```bash",
    "python3 -m http.server 5178",
    "```",
    "",
    "Open `http://127.0.0.1:5178/` from this directory. If the port is busy, use another port and set `BASE_URL` to match.",
    "",
    "## Verify",
    "",
    "From the project root, run:",
    "",
    "```bash",
    "node scripts/verify-release.mjs",
    "node scripts/audit-release-readiness.mjs --run-gates",
    "BASE_URL=http://127.0.0.1:5178 node scripts/smoke-chrome.mjs",
    "BASE_URL=http://127.0.0.1:5178 node scripts/smoke-mobile.mjs",
    "BASE_URL=http://127.0.0.1:5178 node scripts/smoke-interactions.mjs",
    "BASE_URL=http://127.0.0.1:5178 node scripts/smoke-a11y.mjs",
    "node scripts/smoke-release.mjs",
    "```",
    "",
    "Expected result: verification and smoke commands report `status` as `pass`; the smoke output should also have empty `consoleIssues` and `networkIssues`. `smoke-mobile.mjs` must also report empty `layoutIssues`. `smoke-a11y.mjs` must report every keyboard and ARIA check as `true`. `audit-release-readiness.mjs --run-gates` maps release requirements to concrete evidence and reports external publish blockers such as a missing Git remote. `smoke-release.mjs` is the full packaged-release gate: it rebuilds `dist/release`, verifies the manifest, serves the package on a temporary local port, route-smokes the served package, checks the mobile layout, runs the click/input interaction smoke, and runs the keyboard/ARIA accessibility smoke.",
    "",
  ];
  writeFileSync(join(packageDir, "RELEASE.md"), lines.join("\n"), "utf-8");
}

function buildReleaseProvenance(manifest) {
  const manifestSha256 = sha256(join(packageDir, "release-manifest.json"));
  const releaseNotesPath = join(packageDir, "RELEASE.md");
  const totalBytes = manifest.files.reduce((sum, file) => sum + file.bytes, 0);
  const sourceDirtyFiles = Array.isArray(manifest.source?.dirtyFiles) ? manifest.source.dirtyFiles : [];
  const finishedOn = new Date().toISOString();

  return {
    _type: provenanceStatementType,
    subject: [
      {
        name: "release-manifest.json",
        digest: { sha256: manifestSha256 },
        mediaType: "application/json",
      },
    ],
    predicateType: provenancePredicateType,
    predicate: {
      buildDefinition: {
        buildType: provenanceBuildType,
        externalParameters: {
          releaseOutDir: relative(root, outDir).replaceAll("\\", "/"),
          sourceCommit: manifest.sourceCommit,
          sourceBranch: manifest.source?.branch || "unknown",
          sourceDirty: manifest.source?.dirty === true,
          sourceDirtyFiles,
        },
        internalParameters: {
          packageScript: "scripts/package-release.mjs",
          manifestPath: "release-manifest.json",
          provenancePath: "release-provenance.json",
          runtimeFileCount: manifest.files.length,
          totalBytes,
        },
        resolvedDependencies: [
          {
            name: "source-tree",
            uri: "git+file://./",
            digest: { gitCommit: manifest.sourceCommit },
            annotations: {
              "joopark.sourceBranch": manifest.source?.branch || "unknown",
              "joopark.sourceDirty": manifest.source?.dirty === true,
              "joopark.sourceDirtyFileCount": sourceDirtyFiles.length,
            },
          },
          ...sourceEntries.map((entry) => sourceEntryResource(entry)),
        ],
      },
      runDetails: {
        builder: {
          id: provenanceBuilderId,
          version: {
            node: process.version,
            packageScript: "1",
          },
        },
        metadata: {
          invocationId: `joopark-release-${process.pid}-${Date.now()}`,
          startedOn: manifest.generatedAt,
          finishedOn,
        },
        byproducts: [
          {
            name: "release-manifest.json",
            digest: { sha256: manifestSha256 },
            mediaType: "application/json",
          },
          {
            name: "RELEASE.md",
            digest: { sha256: sha256(releaseNotesPath) },
            mediaType: "text/markdown",
          },
        ],
      },
      joopark_release: {
        signed: false,
        signatureStatus: "unsigned-local-provenance",
        strongerExternalReference: "GitHub artifact attestations can sign release artifacts after workflow installation.",
        manifestSubjectDigest: manifestSha256,
        runtimeFileCount: manifest.files.length,
        totalBytes,
      },
    },
  };
}

function writeReleaseProvenance(manifest) {
  const provenance = buildReleaseProvenance(manifest);
  writeFileSync(join(packageDir, "release-provenance.json"), `${JSON.stringify(provenance, null, 2)}\n`, "utf-8");
  return provenance;
}

function writeDeploySupportFiles() {
  copyFileSync(join(packageDir, "index.html"), join(packageDir, "404.html"));
  writeFileSync(join(packageDir, "_redirects"), [
    "# Netlify fallback for static SPA deployments.",
    "# Existing files are served normally; unmatched direct paths rewrite to the app shell.",
    "/* /index.html 200",
    "",
  ].join("\n"), "utf-8");
  writeFileSync(join(packageDir, "_headers"), [
    "/*",
    "  X-Content-Type-Options: nosniff",
    "  X-Frame-Options: DENY",
    "  Referrer-Policy: strict-origin-when-cross-origin",
    "  Permissions-Policy: camera=(), microphone=(), geolocation=()",
    `  Content-Security-Policy: ${contentSecurityPolicyHeader}`,
    "/vendor/*",
    "  Cache-Control: public, max-age=31536000, immutable",
    "/search-empty-state.js",
    "  Cache-Control: no-cache",
    "/calendar-view.js",
    "  Cache-Control: no-cache",
    "/todo-view.js",
    "  Cache-Control: no-cache",
    "/notes-view.js",
    "  Cache-Control: no-cache",
    "/habits-view.js",
    "  Cache-Control: no-cache",
    "/stats-view.js",
    "  Cache-Control: no-cache",
    "/llm-wiki-view.js",
    "  Cache-Control: no-cache",
    "/portfolio-view.js",
    "  Cache-Control: no-cache",
    "/kanban-view.js",
    "  Cache-Control: no-cache",
    "/gantt-view.js",
    "  Cache-Control: no-cache",
    "/team-view.js",
    "  Cache-Control: no-cache",
    "/workspace-storage.js",
    "  Cache-Control: no-cache",
    "/dashboard-storage.js",
    "  Cache-Control: no-cache",
    "/dashboard-prioritization.js",
    "  Cache-Control: no-cache",
    "/dashboard-evidence-receipts.js",
    "  Cache-Control: no-cache",
    "/dashboard-insights-engine.js",
    "  Cache-Control: no-cache",
    "/dashboard-autoresearch-loop.js",
    "  Cache-Control: no-cache",
    "/dashboard-view.js",
    "  Cache-Control: no-cache",
    "/storage-status-view.js",
    "  Cache-Control: no-cache",
    "/settings-view.js",
    "  Cache-Control: no-cache",
    "/system-status-view.js",
    "  Cache-Control: no-cache",
    "/backup-import-guards.js",
    "  Cache-Control: no-cache",
    "/backup-import-ui.js",
    "  Cache-Control: no-cache",
    "/release-status.js",
    "  Cache-Control: no-cache",
    "/operations-copy-actions.js",
    "  Cache-Control: no-cache",
    "/verify-workspace-summary.js",
    "  Cache-Control: no-cache",
    "/dialog-shell.js",
    "  Cache-Control: no-cache",
    "/project-picker.js",
    "  Cache-Control: no-cache",
    "/global-search.js",
    "  Cache-Control: no-cache",
    "/command-palette.js",
    "  Cache-Control: no-cache",
    "/keyboard-shortcuts.js",
    "  Cache-Control: no-cache",
    "/interaction-setup.js",
    "  Cache-Control: no-cache",
    "/event-reminders.js",
    "  Cache-Control: no-cache",
    "/footer-clock.js",
    "  Cache-Control: no-cache",
    "/db-catalog.js",
    "  Cache-Control: no-cache",
    "/review-handoff.js",
    "  Cache-Control: no-cache",
    "/review-result-view.js",
    "  Cache-Control: no-cache",
    "/review-execution-checklist.js",
    "  Cache-Control: no-cache",
    "/review-issue-payload.js",
    "  Cache-Control: no-cache",
    "/review-result-state.js",
    "  Cache-Control: no-cache",
    "/review-result-draft-state.js",
    "  Cache-Control: no-cache",
    "/review-creation-actions.js",
    "  Cache-Control: no-cache",
    "/review-package-view.js",
    "  Cache-Control: no-cache",
    "/review-artifact-view.js",
    "  Cache-Control: no-cache",
    "/review-artifact-state.js",
    "  Cache-Control: no-cache",
    "/review-copy-actions.js",
    "  Cache-Control: no-cache",
    "/review-submission-copy.js",
    "  Cache-Control: no-cache",
    "/review-recommendation-export.js",
    "  Cache-Control: no-cache",
    "/runtime-error-boundary.js",
    "  Cache-Control: no-cache",
    "/pwa-runtime.js",
    "  Cache-Control: no-cache",
    "/workspace-seed-data.js",
    "  Cache-Control: no-cache",
    "/home-view.js",
    "  Cache-Control: no-cache",
    "/ops-runtime-loader.js",
    "  Cache-Control: no-cache",
    "/app.js",
    "  Cache-Control: no-cache",
    "/sw.js",
    "  Cache-Control: no-cache",
    "/styles.css",
    "  Cache-Control: no-cache",
    "/index.html",
    "  Cache-Control: no-cache",
    "/404.html",
    "  Cache-Control: no-cache",
    "/autoresearch-results/release-readiness-summary.json",
    "  Cache-Control: no-cache",
    "/autoresearch-results/verify-workspace-summary.json",
    "  Cache-Control: no-cache",
    "",
  ].join("\n"), "utf-8");
  writeFileSync(join(packageDir, "vercel.json"), `${JSON.stringify({
    $schema: "https://openapi.vercel.sh/vercel.json",
    cleanUrls: false,
    trailingSlash: false,
    headers: [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Content-Security-Policy", value: contentSecurityPolicyHeader },
        ],
      },
      {
        source: "/vendor/(.*)",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
      {
        source: "/(search-empty-state.js|home-execution-view.js|calendar-view.js|todo-view.js|notes-view.js|habits-view.js|stats-view.js|llm-wiki-view.js|portfolio-view.js|kanban-view.js|gantt-view.js|team-view.js|workspace-storage.js|dashboard-storage.js|dashboard-prioritization.js|dashboard-evidence-receipts.js|dashboard-insights-engine.js|dashboard-autoresearch-loop.js|dashboard-view.js|storage-status-view.js|settings-view.js|system-status-view.js|backup-import-guards.js|backup-import-ui.js|release-status.js|operations-copy-actions.js|verify-workspace-summary.js|dialog-shell.js|project-picker.js|global-search.js|command-palette.js|keyboard-shortcuts.js|interaction-setup.js|event-reminders.js|footer-clock.js|db-catalog.js|review-handoff.js|review-result-view.js|review-execution-checklist.js|review-issue-payload.js|review-result-state.js|review-result-draft-state.js|review-creation-actions.js|review-package-view.js|review-artifact-view.js|review-artifact-state.js|review-copy-actions.js|review-submission-copy.js|review-recommendation-export.js|runtime-error-boundary.js|pwa-runtime.js|workspace-seed-data.js|home-view.js|ops-runtime-loader.js|app.js|sw.js|styles.css|index.html|404.html|autoresearch-results/release-readiness-summary.json|autoresearch-results/verify-workspace-summary.json)",
        headers: [
          { key: "Cache-Control", value: "no-cache" },
        ],
      },
    ],
  }, null, 2)}\n`, "utf-8");
}

function sleepSync(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function readPackageLockOwner(path) {
  try {
    return JSON.parse(readFileSync(join(path, "owner.json"), "utf-8"));
  } catch {
    return {};
  }
}

function packageLockOwnerProcess(owner) {
  const pid = Number(owner?.pid);
  if (!Number.isInteger(pid) || pid <= 0) {
    return { alive: false, commandMatches: false, reason: "invalid_owner_pid" };
  }
  try {
    process.kill(pid, 0);
  } catch (error) {
    if (error?.code === "EPERM") {
      return { alive: true, commandMatches: true, reason: "owner_process_permission_denied" };
    }
    return { alive: false, commandMatches: false, reason: "owner_process_missing" };
  }
  try {
    const command = execFileSync("ps", ["-p", String(pid), "-o", "command="], {
      encoding: "utf-8",
      timeout: 2000,
    }).trim();
    const commandMatches = command.includes("scripts/package-release.mjs");
    return {
      alive: true,
      command,
      commandMatches,
      reason: commandMatches ? "owner_process_active" : "owner_pid_reused",
    };
  } catch {
    return { alive: true, command: "", commandMatches: true, reason: "owner_process_command_unknown" };
  }
}

function lockIsStale(path) {
  try {
    const ageMs = Date.now() - statSync(path).mtimeMs;
    const ownerProcess = packageLockOwnerProcess(readPackageLockOwner(path));
    if (ownerProcess.alive && ownerProcess.commandMatches) return false;
    return ageMs > packageLockStaleMs;
  } catch {
    return false;
  }
}

function acquirePackageLock() {
  mkdirSync(dirname(packageLockDir), { recursive: true });
  const started = Date.now();
  while (true) {
    try {
      mkdirSync(packageLockDir);
      writeFileSync(join(packageLockDir, "owner.json"), `${JSON.stringify({
        pid: process.pid,
        startedAt: new Date().toISOString(),
        outDir: relative(root, outDir),
      }, null, 2)}\n`, "utf-8");
      return;
    } catch (error) {
      if (error && error.code !== "EEXIST") throw error;
      if (lockIsStale(packageLockDir)) {
        rmSync(packageLockDir, { recursive: true, force: true });
        continue;
      }
      if (Date.now() - started > packageLockTimeoutMs) {
        throw new Error(`Timed out waiting for release package lock: ${relative(root, packageLockDir)}`);
      }
      sleepSync(100);
    }
  }
}

function releasePackageLock() {
  rmSync(packageLockDir, { recursive: true, force: true });
}

function publishStagingDir(stagingDir) {
  const previousDir = `${outDir}.previous-${process.pid}-${Date.now()}`;
  rmSync(previousDir, { recursive: true, force: true });
  if (existsSync(outDir)) renameSync(outDir, previousDir);
  try {
    renameSync(stagingDir, outDir);
  } catch (error) {
    if (existsSync(previousDir) && !existsSync(outDir)) renameSync(previousDir, outDir);
    throw error;
  }
  rmSync(previousDir, { recursive: true, force: true });
}

function buildRelease() {
  const stagingDir = `${outDir}.staging-${process.pid}-${Date.now()}`;
  packageDir = stagingDir;
  rmSync(stagingDir, { recursive: true, force: true });
  mkdirSync(stagingDir, { recursive: true });
  try {
    for (const entry of sourceEntries) copyEntry(entry);
    for (const entry of generatedEvidenceEntries) copyOrGenerateEvidenceEntry(entry);
    versionRuntimeAssetRefs();
    writeDeploySupportFiles();
    const manifest = buildManifest();
    writeReleaseNotes(manifest);
    manifest.files = buildManifest().files;
    writeFileSync(join(stagingDir, "release-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf-8");
    writeReleaseProvenance(manifest);
    publishStagingDir(stagingDir);
    return manifest;
  } catch (error) {
    rmSync(stagingDir, { recursive: true, force: true });
    throw error;
  } finally {
    packageDir = outDir;
  }
}

acquirePackageLock();
let manifest;
try {
  manifest = buildRelease();
} finally {
  releasePackageLock();
}

console.log(JSON.stringify({
  status: "pass",
  output: relative(root, outDir),
  files: manifest.files.length,
  bytes: manifest.files.reduce((sum, file) => sum + file.bytes, 0),
}, null, 2));
