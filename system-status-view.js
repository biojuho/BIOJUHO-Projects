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

    function totalTableCount(schemas) {
      return listOf(schemas).reduce((sum, schema) => {
        return sum + listOf(schema.databases).reduce((dbSum, db) => dbSum + listOf(db.tables).length, 0);
      }, 0);
    }

    function systemStatusModel(input) {
      const data = input || {};
      const dashboard = data.dashboard && typeof data.dashboard === "object" ? data.dashboard : {};
      const systemState = data.state && typeof data.state === "object" ? data.state : {};
      const health = data.health && typeof data.health === "object" ? data.health : {};
      const pwaRuntime = data.pwaRuntime && typeof data.pwaRuntime === "object" ? data.pwaRuntime : {};
      const storageView = storageStatusModel(health);
      const projects = listOf(dashboard.projects);
      const adoptionCandidates = projects.filter((project) => project.sourceKind === "adoption-candidate");
      const sourceBacked = adoptionCandidates.filter((project) => safeGithubUrl(project.url) && shortCommit(project.lastCommit));
      const benchmarkContexts = adoptionCandidates.map((project) => projectBenchmarkContext(project));
      const benchmarkFocused = benchmarkContexts.filter((context) => context.any);
      const publishItems = listOf(data.publishItems).length ? listOf(data.publishItems) : publishReadinessItems();
      const publishBlockers = publishItems.filter((item) => item.state === "blocked");
      const alerts = listOf(data.alerts);
      const snapshotHealth = systemState.projectSnapshotHealth && typeof systemState.projectSnapshotHealth === "object"
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
      return html`
        <section class="panel" data-system-operational-surface>
          <div class="panel-head"><div><h2>운영 표면</h2></div></div>
          <dl class="storage-grid">
            ${raw(systemMetricHTML("프로젝트", `${model.projects.length}개`))}
            ${raw(systemMetricHTML("소스 근거", `${model.sourceBacked.length}개`))}
            ${raw(systemMetricHTML("벤치 포커스", `${model.benchmarkFocused.length}개`))}
            ${raw(systemMetricHTML("벤치 분포", `PM ${model.pmBenchmarkCount} · Workspace ${model.workspaceBenchmarkCount} · KB/IA ${model.knowledgeBaseBenchmarkCount}`))}
            ${raw(systemMetricHTML("이슈", `${listOf(dashboard.issues).length}개`))}
            ${raw(systemMetricHTML("DB 카탈로그 정상", `${model.healthyDbCount}/${listOf(dashboard.dbInstances).length}`))}
            ${raw(systemMetricHTML("테이블", `${model.totalTables}개`))}
            ${raw(systemMetricHTML("질의 경고", `${model.slowQueries.length}건`))}
            ${raw(systemMetricHTML("대기 마이그", `${model.pendingMigrations.length}건`))}
          </dl>
        </section>
      `;
    }

    function projectSnapshotHealthHTML(health) {
      const source = health && typeof health === "object" ? health : {};
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
            ${raw(systemMetricHTML("loaded sources", `${loadedCount}/${sourceCount}`))}
            ${raw(systemMetricHTML("merged projects", projectCount))}
            ${raw(systemMetricHTML("applied", source.applied ? "true" : "false"))}
            ${raw(systemMetricHTML("reason", source.appliedReason || "not checked"))}
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

    function pwaRuntimeHTML(model) {
      const runtime = model.pwaRuntime || {};
      const status = runtime.status || "checking";
      const statusLabel = pwaRuntimeLabel(status);
      const tone = pwaRuntimeTone(status);
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
            ${raw(systemMetricHTML("secure context", yesNo(runtime.secureContext || runtime.localHostContext)))}
            ${raw(systemMetricHTML("service worker", runtime.serviceWorkerActive ? "active" : runtime.serviceWorkerSupported ? "waiting" : "unsupported"))}
            ${raw(systemMetricHTML("app shell cache", runtime.cacheReady ? `${runtime.cachedAssetCount || 0} assets` : runtime.cachesSupported ? "waiting" : "unsupported"))}
            ${raw(systemMetricHTML("manifest", yesNo(runtime.manifestLinked)))}
            ${raw(systemMetricHTML("standalone", yesNo(runtime.standalone)))}
            ${raw(systemMetricHTML("network", runtime.online === false ? "offline" : "online"))}
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
        ${raw(pwaRuntimeHTML(model))}
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
      pwaRuntimeHTML,
      publishReadinessPanelHTML,
      renderSystemStatusHTML,
    };
  }

  root.JooParkSystemStatusView = {
    version: VERSION,
    create: createSystemStatusView,
  };
})(window);
