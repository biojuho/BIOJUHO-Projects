(function (root) {
  "use strict";

  const VERSION = "joopark-system-status-view/v1";

  function createSystemStatusView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const kpiCard = typeof options.kpiCard === "function" ? options.kpiCard : function () { return ""; };
    const formatBytes = typeof options.formatBytes === "function" ? options.formatBytes : function (bytes) { return String(bytes); };
    const storageStatusModel = typeof options.storageStatusModel === "function" ? options.storageStatusModel : function () {
      return { localBytes: 0, tone: "ok", statusLabel: "정상" };
    };
    const systemStorageHealthHTML = typeof options.systemStorageHealthHTML === "function" ? options.systemStorageHealthHTML : function () { return ""; };
    const safeGithubUrl = typeof options.safeGithubUrl === "function" ? options.safeGithubUrl : function () { return false; };
    const shortCommit = typeof options.shortCommit === "function" ? options.shortCommit : function () { return ""; };
    const projectBenchmarkContext = typeof options.projectBenchmarkContext === "function" ? options.projectBenchmarkContext : function () {
      return { any: false, pm: false, workspace: false, knowledgeBase: false };
    };
    const publishReadinessItems = typeof options.publishReadinessItems === "function" ? options.publishReadinessItems : function () { return []; };
    const publishUnblockHandoffText = typeof options.publishUnblockHandoffText === "function" ? options.publishUnblockHandoffText : function () { return ""; };
    const publishReadinessListHTML = typeof options.publishReadinessListHTML === "function" ? options.publishReadinessListHTML : function () { return ""; };
    const workflowUiInstallPlanHTML = typeof options.workflowUiInstallPlanHTML === "function" ? options.workflowUiInstallPlanHTML : function () { return ""; };
    const publishDispatchPlanHTML = typeof options.publishDispatchPlanHTML === "function" ? options.publishDispatchPlanHTML : function () { return ""; };
    const remoteWorkflowFileCheckHTML = typeof options.remoteWorkflowFileCheckHTML === "function" ? options.remoteWorkflowFileCheckHTML : function () { return ""; };
    const launchExecutionPacketHTML = typeof options.launchExecutionPacketHTML === "function" ? options.launchExecutionPacketHTML : function () { return ""; };
    const launchReadinessRefreshHTML = typeof options.launchReadinessRefreshHTML === "function" ? options.launchReadinessRefreshHTML : function () { return '<div data-system-launch-readiness-refresh hidden></div>'; };
    const verifyWorkspaceSummaryHTML = typeof options.verifyWorkspaceSummaryHTML === "function" ? options.verifyWorkspaceSummaryHTML : function () { return '<div data-system-verify-workspace-summary hidden></div>'; };
    const releaseGateCacheHTML = typeof options.releaseGateCacheHTML === "function" ? options.releaseGateCacheHTML : function () { return '<div data-system-release-gate-cache hidden></div>'; };
    const releaseProvenanceHTML = typeof options.releaseProvenanceHTML === "function" ? options.releaseProvenanceHTML : function () { return '<div data-system-release-provenance hidden></div>'; };
    const pagesAttestationProofIntakeHTML = typeof options.pagesAttestationProofIntakeHTML === "function" ? options.pagesAttestationProofIntakeHTML : function () { return '<div data-system-pages-attestation-proof-intake hidden></div>'; };
    const publishEvidenceHTML = typeof options.publishEvidenceHTML === "function" ? options.publishEvidenceHTML : function () { return ""; };
    const outputQualityAuditHTML = typeof options.outputQualityAuditHTML === "function" ? options.outputQualityAuditHTML : function () { return ""; };
    const systemDashboardReceiptHTML = typeof options.systemDashboardReceiptHTML === "function" ? options.systemDashboardReceiptHTML : function () { return ""; };

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("system status view requires html and raw helpers");
    }

    function listOf(value) {
      return Array.isArray(value) ? value : [];
    }

    function finiteNumber(value, fallback) {
      const number = Number(value);
      return Number.isFinite(number) ? number : fallback;
    }

    function isObjectValue(value) {
      return Boolean(value && typeof value === "object");
    }

    function totalTableCount(schemas) {
      return listOf(schemas).reduce((sum, schema) => {
        return sum + listOf(schema.databases).reduce((dbSum, db) => dbSum + listOf(db.tables).length, 0);
      }, 0);
    }

    function systemStatusModel(input) {
      const data = input || {};
      const dashboard = isObjectValue(data.dashboard) ? data.dashboard : {};
      const systemState = isObjectValue(data.state) ? data.state : {};
      const health = isObjectValue(data.health) ? data.health : {};
      const pwaRuntime = isObjectValue(data.pwaRuntime) ? data.pwaRuntime : {};
      const opsRuntime = isObjectValue(data.opsRuntime) ? data.opsRuntime : {};
      const storageView = storageStatusModel(health);
      const projects = listOf(dashboard.projects);
      const adoptionCandidates = projects.filter((project) => project.sourceKind === "adoption-candidate");
      const sourceBacked = adoptionCandidates.filter((project) => safeGithubUrl(project.url) && shortCommit(project.lastCommit));
      const benchmarkContexts = adoptionCandidates.map((project) => projectBenchmarkContext(project));
      const benchmarkFocused = benchmarkContexts.filter((context) => context.any);
      const publishItems = listOf(data.publishItems).length ? listOf(data.publishItems) : publishReadinessItems();
      const publishBlockers = publishItems.filter((item) => item.state === "blocked");
      const alerts = listOf(data.alerts);
      const snapshotHealth = isObjectValue(systemState.projectSnapshotHealth)
        ? systemState.projectSnapshotHealth
        : {};

      return {
        dashboard,
        state: systemState,
        health,
        storageView,
        routeCount: finiteNumber(data.routeCount, 0),
        projects,
        adoptionCandidates,
        sourceBacked,
        benchmarkFocused,
        pmBenchmarkCount: benchmarkContexts.filter((context) => context.pm).length,
        workspaceBenchmarkCount: benchmarkContexts.filter((context) => context.workspace).length,
        knowledgeBaseBenchmarkCount: benchmarkContexts.filter((context) => context.knowledgeBase).length,
        pendingMigrations: listOf(dashboard.migrations).filter((migration) => migration.status === "pending"),
        slowQueries: listOf(dashboard.queries).filter((query) => Number(query.p95Ms || query.avgMs || 0) >= 300),
        alerts,
        alertCount: finiteNumber(data.alertCount, alerts.length),
        healthyDbCount: listOf(dashboard.dbInstances).filter((instance) => instance.health === "green").length,
        publishItems,
        publishBlockers,
        publishUnblockHandoff: data.publishUnblockHandoff || publishUnblockHandoffText(),
        snapshotHealth,
        pwaRuntime,
        opsRuntime,
        totalTables: totalTableCount(dashboard.schemas),
      };
    }

    function systemStatusViewModel(input) {
      return systemStatusModel(input);
    }

    function storageColor(tone) {
      return tone === "error" ? "#ff4d5e" : tone === "warn" ? "#f7a928" : "#17d983";
    }

    function storageBadge(tone) {
      return tone === "error" || tone === "warn" ? "!" : "OK";
    }

    function systemMetricHTML(label, value) {
      return html`<div><dt>${label}</dt><dd>${value}</dd></div>`;
    }

    function systemMetricsHTML(items) {
      return listOf(items).map((item) => systemMetricHTML(item.label, item.value)).join("");
    }

    function systemKpisHTML(model) {
      const storageView = model.storageView;
      const snapshotHealth = model.snapshotHealth;
      const kpis = [
        { title: "라우트", value: "#system", unit: "", color: "#2387ff", badge: "#", delta: `${model.routeCount}개 화면` },
        { title: "저장소", value: storageView.statusLabel, unit: "", color: storageColor(storageView.tone), badge: storageBadge(storageView.tone), delta: formatBytes(storageView.localBytes) },
        { title: "후보 스냅샷", value: `${model.sourceBacked.length}/${model.adoptionCandidates.length}`, unit: "개", color: "#22d3ee", badge: "SRC", delta: `asset ${snapshotHealth.loadedCount || 0}/${snapshotHealth.sourceCount || 0} · 벤치 ${model.benchmarkFocused.length}개` },
        { title: "알림", value: String(model.alertCount), unit: "건", color: model.alertCount > 0 ? "#f7a928" : "#17d983", badge: "OPS", delta: `전체 ${model.alerts.length}건` },
      ];
      return html`
        <section class="kpis kpis-4" data-system-status data-system-status-module="${VERSION}" data-system-status-view-module="${VERSION}" data-system-route-count="${model.routeCount}" data-system-source-backed-candidates="${model.sourceBacked.length}" data-system-benchmark-count="${model.benchmarkFocused.length}" data-system-publish-blockers="${model.publishBlockers.length}" data-system-publish-ready="${model.publishBlockers.length === 0 ? "true" : "false"}">
          ${raw(kpis.map((item) => kpiCard(item)).join(""))}
        </section>
      `;
    }

    function operationalSurfaceHTML(model) {
      const dashboard = model.dashboard;
      const metrics = [
        { label: "프로젝트", value: `${model.projects.length}개` },
        { label: "소스 근거", value: `${model.sourceBacked.length}개` },
        { label: "벤치 포커스", value: `${model.benchmarkFocused.length}개` },
        { label: "벤치 분포", value: `PM ${model.pmBenchmarkCount} · Workspace ${model.workspaceBenchmarkCount} · KB/IA ${model.knowledgeBaseBenchmarkCount}` },
        { label: "이슈", value: `${listOf(dashboard.issues).length}개` },
        { label: "DB 카탈로그 정상", value: `${model.healthyDbCount}/${listOf(dashboard.dbInstances).length}` },
        { label: "테이블", value: `${model.totalTables}개` },
        { label: "질의 경고", value: `${model.slowQueries.length}건` },
        { label: "대기 마이그", value: `${model.pendingMigrations.length}건` },
      ];
      return html`
        <section class="panel" data-system-operational-surface>
          <div class="panel-head"><div><h2>운영 표면</h2></div></div>
          <dl class="storage-grid">
            ${raw(systemMetricsHTML(metrics))}
          </dl>
        </section>
      `;
    }

    function projectSnapshotHealthHTML(health) {
      const source = isObjectValue(health) ? health : {};
      const sources = listOf(source.sources);
      const checked = !!source.checked;
      const loadedCount = finiteNumber(source.loadedCount, 0);
      const sourceCount = finiteNumber(source.sourceCount, sources.length);
      const errorCount = finiteNumber(source.errorCount, sources.filter((item) => !item.loaded).length);
      const projectCount = finiteNumber(source.projectCount, 0);
      const tone = !checked ? "warn" : errorCount > 0 ? "warn" : loadedCount > 0 ? "ok" : "error";
      const statusLabel = !checked ? "checking" : errorCount > 0 ? "partial" : loadedCount > 0 ? "loaded" : "unavailable";
      const rows = sources.length ? sources : [
        { path: "data/repos.json", loaded: false, status: "not checked", projectCount: 0 },
        { path: "data/adoption-candidates.json", loaded: false, status: "not checked", projectCount: 0 },
      ];
      const metrics = [
        { label: "loaded sources", value: `${loadedCount}/${sourceCount}` },
        { label: "merged projects", value: projectCount },
        { label: "applied", value: source.applied ? "true" : "false" },
        { label: "reason", value: source.appliedReason || "not checked" },
      ];

      return html`
        <section class="panel" role="status" aria-live="polite" data-system-source-snapshots data-source-snapshot-status="${statusLabel}" data-source-snapshot-tone="${tone}" data-source-snapshot-loaded="${loadedCount > 0 ? "true" : "false"}" data-source-snapshot-loaded-count="${loadedCount}" data-source-snapshot-source-count="${sourceCount}" data-source-snapshot-error-count="${errorCount}" data-source-snapshot-project-count="${projectCount}" data-source-snapshot-applied="${source.applied ? "true" : "false"}" data-source-snapshot-applied-reason="${source.appliedReason || ""}">
          <div class="panel-head">
            <div>
              <h2>Source snapshot health</h2>
              <p>정적 JSON 후보/저장소 seed asset 로드 상태</p>
            </div>
            <span class="publish-state" data-source-snapshot-status-label>${statusLabel}</span>
          </div>
          <dl class="storage-grid">
            ${raw(systemMetricsHTML(metrics))}
          </dl>
          <ul class="settings-info" data-source-snapshot-list>
            ${raw(rows.map((item) => html`
              <li data-source-snapshot-row data-source-snapshot-path="${item.path || ""}" data-source-snapshot-row-status="${item.status || ""}" data-source-snapshot-row-loaded="${item.loaded ? "true" : "false"}">
                <strong>${item.path || "unknown"}</strong> · ${item.status || "unknown"} · ${item.projectCount || 0} projects${item.error ? ` · ${item.error}` : ""}
              </li>
            `).join(""))}
          </ul>
        </section>
      `;
    }

    function githubProjectDiscoveryModel(source) {
      const state = isObjectValue(source) ? source : {};
      const data = isObjectValue(state.data) ? state.data : {};
      const counts = isObjectValue(data.counts) ? data.counts : {};
      const freshness = isObjectValue(data.freshnessEvidence) ? data.freshnessEvidence : {};
      const localScan = isObjectValue(data.localScan) ? data.localScan : {};
      const projects = listOf(data.rankedProjects);
      const loaded = state.loaded === true && data.status === "pass";
      const privateMetadataExposure = finiteNumber(data.privacy?.privateGithubMetadataExposure, 0);
      const privateRowExposure = finiteNumber(data.privacy?.privateGithubRowExposure, 0);
      const privateMetadataReady = data.privacy?.privateGithubMetadataRedacted === true && privateMetadataExposure === 0 && privateRowExposure === 0;
      const publicSafe = data.privacy?.publicArtifactSafe === true && data.privacy?.absoluteLocalPathExposure === false && privateMetadataReady;
      const sourceFields = listOf(freshness.sourceFields);
      const ignoredDirectoryNames = listOf(localScan.ignoredDirectoryNames);
      return {
        source: state.source || "data/github-project-discovery.json",
        loaded,
        checked: state.checked === true,
        statusLabel: !state.checked ? "checking" : loaded ? "loaded" : "unavailable",
        generatedAt: data.generatedAt || "",
        owner: data.owner || "unknown",
        localRoot: data.localRoot || "<local-root>",
        localPathMode: data.localPathMode || data.privacy?.localPathMode || "unknown",
        localRepos: finiteNumber(counts.localGitRepos, 0),
        githubRepos: finiteNumber(counts.githubRepos, 0),
        rankedProjects: finiteNumber(counts.rankedProjects, projects.length),
        dirtyRepos: finiteNumber(counts.localDirtyRepos, 0),
        privateGithubRepos: finiteNumber(data.privacy?.privateGithubRepoCount, finiteNumber(counts.privateGithubRepos, 0)),
        privateLocalRemotes: finiteNumber(data.privacy?.privateLocalRemoteCount, finiteNumber(counts.privateLocalRemotes, 0)),
        privateRankedRowsRedacted: finiteNumber(data.privacy?.privateRankedProjectRowsRedacted, finiteNumber(counts.privateRankedProjectRowsRedacted, 0)),
        privateMetadataExposure,
        privateRowExposure,
        privateMetadataReady,
        githubReposWithPushedAt: finiteNumber(freshness.githubReposWithPushedAt, finiteNumber(counts.githubReposWithPushedAt, 0)),
        freshGithubRepos: finiteNumber(freshness.freshGithubRepos, finiteNumber(counts.freshGithubRepos, 0)),
        recentWindowDays: finiteNumber(freshness.recentWindowDays, 30),
        sourceFieldCount: sourceFields.length,
        freshnessReady: freshness.status === "pass" && freshness.rankingUsesPushedAt === true && sourceFields.includes("pushedAt"),
        localScanMaxDepth: finiteNumber(localScan.maxDepth, finiteNumber(data.maxDepth, 0)),
        localScanIgnoredCount: ignoredDirectoryNames.length,
        reproducibleCommand: localScan.reproducibleCommand || "",
        reproducibilityReady: localScan.status === "pass" && localScan.sourceCommandReproducible === true && !!localScan.reproducibleCommand,
        releaseTargetReady: data.releaseTargetReady === true,
        publicSafe,
        guard: data.guard || "read-only discovery only",
        abDecision: data.abComparison?.decision || "",
        projects: projects.slice(0, 6),
        error: state.error || "",
      };
    }

    function githubProjectDiscoveryHTML(source) {
      const model = githubProjectDiscoveryModel(source);
      const tone = model.loaded && model.publicSafe ? "ok" : model.checked ? "warn" : "checking";
      const metrics = [
        { label: "local git", value: `${model.localRepos} repos` },
        { label: "GitHub owner", value: `${model.owner} · ${model.githubRepos} repos` },
        { label: "ranked", value: `${model.rankedProjects} projects` },
        { label: "dirty local", value: `${model.dirtyRepos} repos` },
        { label: "pushedAt coverage", value: `${model.githubReposWithPushedAt}/${model.githubRepos}` },
        { label: `${model.recentWindowDays}d fresh`, value: `${model.freshGithubRepos} repos` },
        { label: "scan replay", value: model.reproducibilityReady ? `${model.localScanMaxDepth} depth` : "needs review" },
        { label: "private metadata", value: model.privateMetadataReady ? `${model.privateGithubRepos + model.privateLocalRemotes} redacted` : "needs review" },
        { label: "private rows", value: model.privateRowExposure === 0 ? `${model.privateRankedRowsRedacted} redacted` : "needs review" },
        { label: "release target", value: yesNo(model.releaseTargetReady) },
        { label: "path privacy", value: model.publicSafe ? model.localPathMode : "needs review" },
      ];
      return html`
        <section class="panel" role="status" aria-live="polite" data-system-github-project-discovery data-github-project-discovery-source="${model.source}" data-github-project-discovery-loaded="${model.loaded ? "true" : "false"}" data-github-project-discovery-public-safe="${model.publicSafe ? "true" : "false"}" data-github-project-discovery-local-count="${model.localRepos}" data-github-project-discovery-github-count="${model.githubRepos}" data-github-project-discovery-ranked-count="${model.rankedProjects}" data-github-project-discovery-release-target-ready="${model.releaseTargetReady ? "true" : "false"}" data-github-project-discovery-ab-decision="${model.abDecision}" data-github-project-discovery-local-path-mode="${model.localPathMode}" data-github-project-discovery-freshness-ready="${model.freshnessReady ? "true" : "false"}" data-github-project-discovery-reproducible="${model.reproducibilityReady ? "true" : "false"}" data-github-project-discovery-private-redacted="${model.privateMetadataReady ? "true" : "false"}" data-github-project-discovery-private-count="${model.privateGithubRepos}" data-github-project-discovery-private-local-remote-count="${model.privateLocalRemotes}" data-github-project-discovery-private-rows-redacted="${model.privateRankedRowsRedacted}" data-github-project-discovery-private-exposure="${model.privateMetadataExposure}" data-github-project-discovery-private-row-exposure="${model.privateRowExposure}" data-github-project-discovery-local-scan-depth="${model.localScanMaxDepth}" data-github-project-discovery-ignored-count="${model.localScanIgnoredCount}" data-github-project-discovery-pushed-count="${model.githubReposWithPushedAt}" data-github-project-discovery-fresh-count="${model.freshGithubRepos}" data-github-project-discovery-source-field-count="${model.sourceFieldCount}" data-github-project-discovery-tone="${tone}">
          <div class="panel-head">
            <div>
              <h2>GitHub project discovery</h2>
              <p>관련 로컬/GitHub 프로젝트 인벤토리와 cross-repo 작업 guard</p>
            </div>
            <span class="publish-state" data-github-project-discovery-status-label>${model.statusLabel}</span>
          </div>
          <dl class="storage-grid">
            ${raw(systemMetricsHTML(metrics))}
          </dl>
          <ul class="settings-info" data-github-project-discovery-list>
            ${raw(model.projects.map((project) => html`
              <li data-github-project-discovery-row data-github-project-discovery-project="${project.nameWithOwner || ""}" data-github-project-discovery-relation="${project.relation || ""}" data-github-project-discovery-local="${project.localCheckout ? "true" : "false"}" data-github-project-discovery-pushed-at="${project.pushedAt || ""}" data-github-project-discovery-stars="${finiteNumber(project.stargazerCount, 0)}">
                <strong>${project.nameWithOwner || "unknown"}</strong> · ${project.relation || "unknown"} · ${project.localCheckout ? project.localPath || "local" : "remote"} · pushed ${project.pushedAt || "unknown"} · stars ${finiteNumber(project.stargazerCount, 0)} · ${project.nextAction || "No next action"}
              </li>
            `).join(""))}
          </ul>
          ${model.reproducibleCommand ? raw(html`<p class="settings-note" data-github-project-discovery-replay><code>${model.reproducibleCommand}</code></p>`) : ""}
          <p class="settings-note" data-github-project-discovery-guard>${model.guard}</p>
          ${model.error ? raw(html`<p class="settings-note" data-github-project-discovery-error>${model.error}</p>`) : ""}
        </section>
      `;
    }

    function pwaRuntimeTone(status) {
      if (status === "ready") return "ok";
      if (status === "partial" || status === "waiting" || status === "checking") return "warn";
      return "error";
    }

    function pwaRuntimeLabel(status) {
      if (status === "ready") return "ready";
      if (status === "partial") return "partial";
      if (status === "waiting") return "waiting";
      if (status === "insecure") return "insecure";
      if (status === "unsupported") return "unsupported";
      return "checking";
    }

    function yesNo(value) {
      return value ? "true" : "false";
    }

    function serviceWorkerRuntimeLabel(runtime) {
      if (runtime.serviceWorkerActive) return "active";
      return runtime.serviceWorkerSupported ? "waiting" : "unsupported";
    }

    function appShellCacheRuntimeLabel(runtime) {
      if (runtime.cacheReady) return `${runtime.cachedAssetCount || 0} assets`;
      return runtime.cachesSupported ? "waiting" : "unsupported";
    }

    function opsRuntimeStatusLabel(runtime, failed, pending, loadedCount, totalCount) {
      if (!runtime.version) return "missing";
      if (failed.length) return "failed";
      if (pending.length) return "loading";
      return totalCount > 0 && loadedCount === totalCount ? "ready" : "partial";
    }

    function pwaRuntimeHTML(model) {
      const runtime = model.pwaRuntime || {};
      const status = runtime.status || "checking";
      const statusLabel = pwaRuntimeLabel(status);
      const tone = pwaRuntimeTone(status);
      const metrics = [
        { label: "secure context", value: yesNo(runtime.secureContext || runtime.localHostContext) },
        { label: "service worker", value: serviceWorkerRuntimeLabel(runtime) },
        { label: "app shell cache", value: appShellCacheRuntimeLabel(runtime) },
        { label: "manifest", value: yesNo(runtime.manifestLinked) },
        { label: "standalone", value: yesNo(runtime.standalone) },
        { label: "network", value: runtime.online === false ? "offline" : "online" },
      ];
      return html`
        <section class="panel pwa-runtime" role="status" aria-live="polite" data-system-pwa-runtime data-pwa-runtime-status="${statusLabel}" data-pwa-runtime-tone="${tone}" data-pwa-runtime-service-worker-active="${yesNo(runtime.serviceWorkerActive)}" data-pwa-runtime-cache-ready="${yesNo(runtime.cacheReady)}" data-pwa-runtime-manifest-linked="${yesNo(runtime.manifestLinked)}" data-pwa-runtime-cached-asset-count="${runtime.cachedAssetCount || 0}" data-pwa-runtime-online="${yesNo(runtime.online !== false)}">
          <div class="panel-head">
            <div>
              <h2>PWA runtime</h2>
              <p>현재 브라우저의 service worker, offline app shell cache, manifest 상태</p>
            </div>
            <span class="publish-state" data-pwa-runtime-status-label>${statusLabel}</span>
          </div>
          <dl class="storage-grid pwa-runtime-grid">
            ${raw(systemMetricsHTML(metrics))}
          </dl>
          <div class="pwa-runtime-details">
            <span><strong>scope</strong> <code data-pwa-runtime-scope>${runtime.scope || "not registered"}</code></span>
            <span><strong>script</strong> <code data-pwa-runtime-script>${runtime.scriptURL || "./sw.js"}</code></span>
            <span><strong>cache</strong> <code data-pwa-runtime-cache>${runtime.appShellCache || "not ready"}</code></span>
            ${runtime.checkedAt ? raw(html`<span><strong>checked</strong> ${runtime.checkedAt}</span>`) : ""}
            ${runtime.lastError ? raw(html`<span data-pwa-runtime-error><strong>error</strong> ${runtime.lastError}</span>`) : ""}
          </div>
        </section>
      `;
    }

    function opsRuntimeHTML(model) {
      const runtime = model.opsRuntime || {};
      const groupStats = listOf(runtime.groupStats);
      const failed = listOf(runtime.failed);
      const pending = listOf(runtime.pending);
      const loadedCount = finiteNumber(runtime.loadedLazyFileCount, 0);
      const totalCount = finiteNumber(runtime.lazyFileCount, groupStats.reduce((sum, group) => sum + finiteNumber(group.total, 0), 0));
      const readyGroups = groupStats.filter((group) => group.ready).length;
      const statusLabel = opsRuntimeStatusLabel(runtime, failed, pending, loadedCount, totalCount);
      const lastGroup = groupStats.find((group) => group.lastStatus && group.lastStatus !== "none") || {};
      const metrics = [
        { label: "loaded lazy files", value: `${loadedCount}/${totalCount}` },
        { label: "ready groups", value: `${readyGroups}/${groupStats.length}` },
        { label: "pending", value: pending.length },
        { label: "failed", value: failed.length },
      ];
      return html`
        <section class="panel ops-runtime-diagnostics" role="status" aria-live="polite" data-system-ops-runtime data-ops-runtime-status="${statusLabel}" data-ops-runtime-version="${runtime.version || "missing"}" data-ops-runtime-loaded-count="${loadedCount}" data-ops-runtime-total-count="${totalCount}" data-ops-runtime-ready-group-count="${readyGroups}" data-ops-runtime-group-count="${groupStats.length}" data-ops-runtime-pending-count="${pending.length}" data-ops-runtime-failed-count="${failed.length}" data-ops-runtime-last-group="${lastGroup.group || ""}" data-ops-runtime-last-status="${lastGroup.lastStatus || "none"}">
          <div class="panel-head">
            <div>
              <h2>Ops runtime diagnostics</h2>
              <p>지연 로드되는 release/review 런타임 파일의 현재 로드 상태</p>
            </div>
            <span class="publish-state" data-ops-runtime-status-label>${statusLabel}</span>
          </div>
          <dl class="storage-grid">
            ${raw(systemMetricsHTML(metrics))}
          </dl>
          <ul class="settings-info" data-ops-runtime-groups>
            ${raw(groupStats.map((group) => html`
              <li data-ops-runtime-group data-ops-runtime-group-name="${group.group || ""}" data-ops-runtime-group-status="${group.status || ""}" data-ops-runtime-group-ready="${group.ready ? "true" : "false"}" data-ops-runtime-group-loaded-count="${group.loadedCount || 0}" data-ops-runtime-group-total="${group.total || 0}" data-ops-runtime-group-failed-count="${group.failedCount || 0}">
                <strong>${group.group || "group"}</strong> · ${group.loadedCount || 0}/${group.total || 0} loaded · ${group.status || "unknown"} · last ${group.lastStatus || "none"}
              </li>
            `).join(""))}
          </ul>
          ${failed.length ? raw(html`
            <ul class="settings-info" data-ops-runtime-failures>
              ${failed.map((item) => raw(html`<li data-ops-runtime-failure data-ops-runtime-failure-path="${item.path || ""}"><strong>${item.path || "unknown"}</strong> · ${item.error || "failed"}</li>`))}
            </ul>
          `) : ""}
        </section>
      `;
    }

    function publishReadinessPanelHTML(model) {
      const state = model.state;
      const blockerCount = model.publishBlockers.length;
      return html`
        <section class="panel publish-readiness" data-system-publish-readiness data-system-publish-blockers="${blockerCount}">
          <div class="panel-head">
            <div><h2>공개 준비 상태</h2></div>
            <small>${blockerCount ? `${blockerCount}개 action required` : "ready"}</small>
          </div>
          <p class="settings-note">검증 완료 항목과 실제 공개 전에 남은 workflow 설치/실행 항목을 분리해서 추적합니다. Settings의 배포 handoff도 같은 항목을 Markdown으로 복사합니다.</p>
          <div class="publish-readiness-actions" data-system-publish-handoff>
            <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-system-publish-handoff" data-system-publish-handoff-copy data-system-publish-handoff-text="${model.publishUnblockHandoff}">publish unblock handoff 복사</button>
            <small class="portfolio-export-status" data-system-publish-handoff-copy-status aria-live="polite"></small>
          </div>
          ${raw(workflowUiInstallPlanHTML(state.workflowUiInstallPlan))}
          ${raw(publishDispatchPlanHTML(state.publishDispatchPlan))}
          ${raw(remoteWorkflowFileCheckHTML(state.remoteWorkflowFileCheck))}
          ${raw(launchExecutionPacketHTML(state.launchExecutionPacket))}
          ${raw(launchReadinessRefreshHTML(state.launchReadinessRefresh))}
          ${raw(verifyWorkspaceSummaryHTML(state.verifyWorkspaceSummary))}
          ${raw(releaseGateCacheHTML(state.releaseReadinessSummary))}
          ${raw(releaseProvenanceHTML(state.releaseProvenance))}
          ${raw(pagesAttestationProofIntakeHTML({
            launchExecutionPacket: state.launchExecutionPacket,
            publishDispatchPlan: state.publishDispatchPlan,
            releaseProvenance: state.releaseProvenance,
          }))}
          ${raw(publishEvidenceHTML(state.publishEvidence))}
          ${raw(outputQualityAuditHTML(state.outputQualityAudit))}
          <div class="publish-readiness-list">
            ${raw(publishReadinessListHTML(model.publishItems))}
          </div>
        </section>
      `;
    }

    function renderSystemStatusHTML(input) {
      const model = systemStatusViewModel(input);
      return html`
        ${raw(systemKpisHTML(model))}
        ${raw(systemStorageHealthHTML(model.health))}
        ${raw(operationalSurfaceHTML(model))}
        ${raw(projectSnapshotHealthHTML(model.snapshotHealth))}
        ${raw(githubProjectDiscoveryHTML(model.state.githubProjectDiscovery))}
        ${raw(pwaRuntimeHTML(model))}
        ${raw(opsRuntimeHTML(model))}
        ${raw(systemDashboardReceiptHTML())}
        ${raw(publishReadinessPanelHTML(model))}
      `;
    }

    return {
      version: VERSION,
      systemStatusModel,
      systemStatusViewModel,
      systemKpisHTML,
      operationalSurfaceHTML,
      projectSnapshotHealthHTML,
      githubProjectDiscoveryHTML,
      pwaRuntimeHTML,
      opsRuntimeHTML,
      publishReadinessPanelHTML,
      renderSystemStatusHTML,
    };
  }

  root.JooParkSystemStatusView = {
    version: VERSION,
    create: createSystemStatusView,
  };
})(window);
