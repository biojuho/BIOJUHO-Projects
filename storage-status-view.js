(function (root) {
  "use strict";

  const VERSION = "joopark-storage-status-view/v1";

  function createStorageStatusView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const formatBytes = typeof options.formatBytes === "function" ? options.formatBytes : function (bytes) { return String(bytes); };
    const formatLocalDateTime = typeof options.formatLocalDateTime === "function" ? options.formatLocalDateTime : function (value) { return value || ""; };
    const storedPayloadBytes = typeof options.storedPayloadBytes === "function" ? options.storedPayloadBytes : function () { return 0; };
    const storagePercent = typeof options.storagePercent === "function" ? options.storagePercent : function () { return null; };
    const storageTone = typeof options.storageTone === "function" ? options.storageTone : function () { return "ok"; };
    const storageStatusLabel = typeof options.storageStatusLabel === "function" ? options.storageStatusLabel : function () { return "정상"; };
    const storagePersistentLabel = typeof options.storagePersistentLabel === "function" ? options.storagePersistentLabel : function () { return "확인 중"; };
    const panelHead = typeof options.panelHead === "function" ? options.panelHead : null;
    const nowISO = typeof options.nowISO === "function" ? options.nowISO : function () { return new Date().toISOString(); };
    const storeKeyV3 = options.storeKeyV3 || "joopark.workspace.v3";

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("storage status view requires html and raw helpers");
    }

    function storageStatusModel(health) {
      const source = isObjectValue(health) ? health : {};
      const artifactSource = isObjectValue(source.artifactStorage) ? source.artifactStorage : {};
      const artifactStatus = artifactSource.available
        ? (artifactSource.status || "ready")
        : "unavailable";
      const artifactLabelMap = {
        ready: "대기",
        pending: "미러링 중",
        mirrored: "미러 완료",
        hydrating: "복원 중",
        hydrated: "복원 완료",
        skipped: "로컬 우선",
        empty: "원격 없음",
        error: "오류",
        unavailable: "미지원",
      };
      const localBytes = Number.isFinite(source.localBytes) ? source.localBytes : storedPayloadBytes();
      const usageBytes = Number.isFinite(source.usageBytes) ? source.usageBytes : localBytes;
      const quotaBytes = Number.isFinite(source.quotaBytes) ? source.quotaBytes : null;
      const usagePct = storagePercent(usageBytes, quotaBytes);
      const usagePctLabel = usagePct === null ? "추정치 없음" : `${usagePct.toFixed(1)}%`;
      const meterWidth = usagePct === null ? 3 : Math.max(3, Math.min(100, usagePct));
      const tone = storageTone(source);
      const statusLabel = storageStatusLabel(source);
      const quotaLabel = quotaBytes ? formatBytes(quotaBytes) : "추정치 없음";
      const lastChecked = source.checkedAt ? formatLocalDateTime(source.checkedAt) : "대기 중";
      const persistedLabel = storagePersistentLabel(source);
      return {
        health: source,
        localBytes,
        usageBytes,
        quotaBytes,
        usagePct,
        usagePctLabel,
        meterWidth,
        tone,
        statusLabel,
        quotaLabel,
        lastChecked,
        persistedLabel,
        artifactStorage: {
          key: artifactSource.key || "joopark-workspace:v3",
          shared: artifactSource.shared === true,
          available: artifactSource.available === true,
          status: artifactStatus,
          label: artifactLabelMap[artifactStatus] || artifactStatus,
          lastMirroredAt: artifactSource.lastMirroredAt || "",
          lastHydratedAt: artifactSource.lastHydratedAt || "",
          lastBytes: Number.isFinite(artifactSource.lastBytes) ? artifactSource.lastBytes : 0,
          lastError: artifactSource.lastError || "",
        },
      };
    }

    function storageMeterHTML(model) {
      return html`
        <div class="storage-meter" aria-label="브라우저 저장소 사용률">
          <span style="width:${raw(model.meterWidth.toFixed(1))}%"></span>
        </div>
      `;
    }

    function storageErrorHTML(model) {
      return model.health.lastError
        ? html`<p class="settings-note storage-error">최근 오류: ${model.health.lastError}</p>`
        : "";
    }

    function artifactStorageErrorHTML(model) {
      return model.artifactStorage && model.artifactStorage.lastError
        ? html`<p class="settings-note storage-error">Artifact mirror 오류: ${model.artifactStorage.lastError}</p>`
        : "";
    }

    function isObjectValue(value) {
      return Boolean(value && typeof value === "object");
    }

    function recoveryDownloadHref(recovery) {
      const text = recovery && recovery.json ? String(recovery.json) : "";
      return text ? `data:application/json;charset=utf-8,${encodeURIComponent(text)}` : "";
    }

    function storageFailureRecoveryHTML(model) {
      const recovery = model.health && isObjectValue(model.health.recovery)
        ? model.health.recovery
        : null;
      if (!recovery || recovery.ready !== true || !recovery.json) return "";
      const href = recoveryDownloadHref(recovery);
      return html`
        <div class="storage-failure-recovery" role="alert" data-storage-failure-recovery data-storage-failure-recovery-ready="true" data-storage-failure-recovery-bytes="${recovery.bytes || 0}" data-storage-failure-recovery-generated-at="${recovery.generatedAt || ""}">
          <strong>저장 실패 복구</strong>
          <p>브라우저 저장소 쓰기에 실패했습니다. 현재 메모리의 데이터를 긴급 백업 JSON으로 먼저 내려받은 뒤 저장소를 정리하세요.</p>
          <div class="storage-failure-actions">
            <a class="primary-btn" href="${href}" download="${recovery.filename || "joopark-workspace-emergency.json"}" data-storage-failure-recovery-download>긴급 백업 다운로드</a>
            <button type="button" data-action="export-data" data-storage-failure-normal-export>일반 백업 내보내기</button>
          </div>
          <small>원인: ${recovery.reason || model.health.lastError || "localStorage write failed"} · ${formatBytes(recovery.bytes || 0)}</small>
        </div>
      `;
    }

    function storageMetricHTML(label, value, attrs = "") {
      const ddAttrs = attrs ? ` ${attrs}` : "";
      return html`<div><dt>${label}</dt><dd${raw(ddAttrs)}>${value}</dd></div>`;
    }

    function storageMetricsHTML(metrics) {
      return metrics.map(([label, value, attrs]) => storageMetricHTML(label, value, attrs)).join("");
    }

    function settingsStorageHealthHTML(health) {
      const model = storageStatusModel(health);
      const metrics = [
        ["상태", model.statusLabel, 'id="storageHealthStatus"'],
        ["저장 데이터", formatBytes(model.localBytes), "data-storage-local"],
        ["브라우저 사용량", formatBytes(model.usageBytes)],
        ["추정 한도", model.quotaLabel],
        ["사용률", model.usagePctLabel],
        ["영속 저장", model.persistedLabel],
        ["Artifact mirror", model.artifactStorage.label, 'data-artifact-storage-status'],
        ["Artifact key", `${model.artifactStorage.key} · shared=${model.artifactStorage.shared ? "true" : "false"}`],
        ["StorageManager", model.health.estimateSupported ? "지원" : "미지원"],
        ["확인 시각", model.lastChecked, 'id="storageHealthUpdated"'],
      ];
      return html`
        <section class="panel storage-health" role="status" aria-live="polite" aria-atomic="true" data-storage-health data-storage-tone="${model.tone}">
          <div class="panel-head">
            <div><h2>저장소 상태</h2></div>
            <div class="settings-actions">
              <button type="button" data-action="refresh-storage-health">새로고침</button>
              <button type="button" class="primary-btn" data-action="request-storage-persistence">영속 저장 요청</button>
            </div>
          </div>
          ${raw(storageMeterHTML(model))}
          <dl class="storage-grid">
            ${raw(storageMetricsHTML(metrics))}
          </dl>
          ${raw(storageErrorHTML(model))}
          ${raw(artifactStorageErrorHTML(model))}
          ${raw(storageFailureRecoveryHTML(model))}
        </section>
      `;
    }

    function systemStorageHealthHTML(health) {
      const model = storageStatusModel(health);
      const heading = panelHead
        ? panelHead("시스템 상태", null, html`<small>${formatLocalDateTime(nowISO())}</small>`)
        : html`<div class="panel-head"><div><h2>시스템 상태</h2></div><small>${formatLocalDateTime(nowISO())}</small></div>`;
      const metrics = [
        ["저장소", model.statusLabel],
        ["저장 데이터", formatBytes(model.localBytes)],
        ["브라우저 사용량", formatBytes(model.usageBytes)],
        ["추정 한도", model.quotaLabel],
        ["사용률", model.usagePctLabel],
        ["영속 저장", model.persistedLabel],
        ["Artifact mirror", model.artifactStorage.label],
        ["Artifact key", `${model.artifactStorage.key} · shared=${model.artifactStorage.shared ? "true" : "false"}`],
        ["확인 시각", model.lastChecked],
        ["localStorage", storeKeyV3],
      ];
      return html`
        <section class="panel storage-health" role="status" aria-live="polite" aria-atomic="true" data-system-storage data-storage-tone="${model.tone}">
          ${raw(heading)}
          ${raw(storageMeterHTML(model))}
          <dl class="storage-grid">
            ${raw(storageMetricsHTML(metrics))}
          </dl>
          ${raw(storageErrorHTML(model))}
          ${raw(artifactStorageErrorHTML(model))}
          ${raw(storageFailureRecoveryHTML(model))}
        </section>
      `;
    }

    return {
      version: VERSION,
      storageStatusModel,
      settingsStorageHealthHTML,
      systemStorageHealthHTML,
      storageFailureRecoveryHTML,
    };
  }

  root.JooParkStorageStatusView = {
    version: VERSION,
    create: createStorageStatusView,
  };
})(window);
