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
      const source = health && typeof health === "object" ? health : {};
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

    function storageMetricHTML(label, value, attrs = "") {
      const ddAttrs = attrs ? ` ${attrs}` : "";
      return html`<div><dt>${label}</dt><dd${raw(ddAttrs)}>${value}</dd></div>`;
    }

    function settingsStorageHealthHTML(health) {
      const model = storageStatusModel(health);
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
            ${raw(storageMetricHTML("상태", model.statusLabel, 'id="storageHealthStatus"'))}
            ${raw(storageMetricHTML("저장 데이터", formatBytes(model.localBytes), "data-storage-local"))}
            ${raw(storageMetricHTML("브라우저 사용량", formatBytes(model.usageBytes)))}
            ${raw(storageMetricHTML("추정 한도", model.quotaLabel))}
            ${raw(storageMetricHTML("사용률", model.usagePctLabel))}
            ${raw(storageMetricHTML("영속 저장", model.persistedLabel))}
            ${raw(storageMetricHTML("StorageManager", model.health.estimateSupported ? "지원" : "미지원"))}
            ${raw(storageMetricHTML("확인 시각", model.lastChecked, 'id="storageHealthUpdated"'))}
          </dl>
          ${raw(storageErrorHTML(model))}
        </section>
      `;
    }

    function systemStorageHealthHTML(health) {
      const model = storageStatusModel(health);
      const heading = panelHead
        ? panelHead("시스템 상태", null, html`<small>${formatLocalDateTime(nowISO())}</small>`)
        : html`<div class="panel-head"><div><h2>시스템 상태</h2></div><small>${formatLocalDateTime(nowISO())}</small></div>`;
      return html`
        <section class="panel storage-health" role="status" aria-live="polite" aria-atomic="true" data-system-storage data-storage-tone="${model.tone}">
          ${raw(heading)}
          ${raw(storageMeterHTML(model))}
          <dl class="storage-grid">
            ${raw(storageMetricHTML("저장소", model.statusLabel))}
            ${raw(storageMetricHTML("저장 데이터", formatBytes(model.localBytes)))}
            ${raw(storageMetricHTML("브라우저 사용량", formatBytes(model.usageBytes)))}
            ${raw(storageMetricHTML("추정 한도", model.quotaLabel))}
            ${raw(storageMetricHTML("사용률", model.usagePctLabel))}
            ${raw(storageMetricHTML("영속 저장", model.persistedLabel))}
            ${raw(storageMetricHTML("확인 시각", model.lastChecked))}
            ${raw(storageMetricHTML("localStorage", storeKeyV3))}
          </dl>
          ${raw(storageErrorHTML(model))}
        </section>
      `;
    }

    return {
      version: VERSION,
      storageStatusModel,
      settingsStorageHealthHTML,
      systemStorageHealthHTML,
    };
  }

  root.JooParkStorageStatusView = {
    version: VERSION,
    create: createStorageStatusView,
  };
})(window);
