(function (root) {
  "use strict";

  const VERSION = "joopark-verify-workspace-summary/v1";
  const SUMMARY_SCHEMA_VERSION = "joopark-verify-workspace/v1";
  const SOURCE = "autoresearch-results/verify-workspace-summary.json";
  const FETCH_SOURCE = `./${SOURCE}`;
  const REQUIRED_STEPS = ["release_readiness_gates", "launch_readiness_refresh", "product_loop_summary_sync"];

  function state(loaded, data, error) {
    return {
      checked: true,
      loaded,
      source: SOURCE,
      data: loaded ? data : null,
      error: loaded ? "" : error,
    };
  }

  function initialState() {
    return {
      checked: false,
      loaded: false,
      source: SOURCE,
      data: null,
      error: "",
    };
  }

  function validStep(step) {
    return step && step.id && step.status === "pass" && typeof step.command === "string";
  }

  function validateSummary(summary) {
    const artifacts = summary?.artifacts || {};
    const evidenceSync = artifacts.evidenceSync || {};
    const stepResults = Array.isArray(summary?.stepResults) ? summary.stepResults : [];
    const stepIds = new Set(stepResults.map((step) => step.id));
    return summary &&
      summary.schemaVersion === SUMMARY_SCHEMA_VERSION &&
      summary.status === "pass" &&
      summary.command === "npm run verify:full" &&
      summary.syncArtifacts === true &&
      summary.evidenceSyncPass === true &&
      REQUIRED_STEPS.every((id) => stepIds.has(id)) &&
      stepResults.every(validStep) &&
      artifacts.releaseReadiness?.status === "pass" &&
      artifacts.launchReadiness?.status === "pass" &&
      artifacts.outputQuality?.status === "pass" &&
      evidenceSync.status === "pass" &&
      evidenceSync.productLoopGateParityReady === true &&
      evidenceSync.productLoopPublishParityReady === true &&
      evidenceSync.summarySyncReady === true;
  }

  function createVerifyWorkspaceSummary(deps) {
    const fetchImpl = typeof deps?.fetch === "function" ? deps.fetch : root.fetch?.bind(root);

    async function load() {
      if (!fetchImpl) return { valid: false, state: state(false, null, "fetch unavailable") };
      try {
        const res = await fetchImpl(FETCH_SOURCE, { cache: "no-store" });
        if (!res.ok) return { valid: false, state: state(false, null, `HTTP ${res.status}`) };
        const summary = await res.json();
        const valid = validateSummary(summary);
        return {
          valid,
          state: state(valid, summary, valid ? "" : "invalid verify workspace summary shape"),
        };
      } catch (err) {
        return { valid: false, state: state(false, null, err.message) };
      }
    }

    return {
      source: SOURCE,
      requiredSteps: REQUIRED_STEPS.slice(),
      initialState,
      validateSummary,
      load,
    };
  }

  root.JooParkVerifyWorkspaceSummary = {
    VERSION,
    version: VERSION,
    create: createVerifyWorkspaceSummary,
  };
})(window);
