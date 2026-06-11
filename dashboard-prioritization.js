/* ================================================================
 * JooPark Workspace — dashboard improvement prioritization.
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkDashboardPrioritization(global) {
  "use strict";

  const VERSION = "joopark-dashboard-prioritization/v1";
  const CRITERIA = Object.freeze([
    "userValue",
    "urgency",
    "difficulty",
    "regressionRisk",
    "performance",
    "accessibility",
    "security",
    "maintainability",
    "releaseReadiness",
    "localStorageStability",
    "mobileUX",
    "evidenceTraceability",
  ]);

  function clampScore(value, fallback = 3) {
    const number = Number(value);
    if (!Number.isFinite(number)) return fallback;
    return Math.max(1, Math.min(5, Math.round(number)));
  }

  function scoreBreakdown(input = {}) {
    return CRITERIA.reduce((out, key) => {
      out[key] = clampScore(input[key]);
      return out;
    }, {});
  }

  function weightedScore(breakdown) {
    const scores = scoreBreakdown(breakdown);
    const upside = (
      scores.userValue * 1.5 +
      scores.urgency * 1.25 +
      scores.performance +
      scores.accessibility +
      scores.security +
      scores.maintainability +
      scores.releaseReadiness * 1.25 +
      scores.localStorageStability * 1.2 +
      scores.mobileUX +
      scores.evidenceTraceability * 1.2
    );
    const drag = (scores.difficulty * 0.8) + (scores.regressionRisk * 0.9);
    return Number(Math.max(1, Math.min(100, ((upside - drag) / 45) * 100)).toFixed(1));
  }

  function rankCandidates(candidates) {
    return (Array.isArray(candidates) ? candidates : [])
      .map((candidate, index) => {
        const score = scoreBreakdown(candidate.scoreBreakdown || {});
        return {
          ...candidate,
          scoreBreakdown: {
            ...score,
            weighted: weightedScore(score),
          },
          rankHint: index + 1,
        };
      })
      .sort((a, b) => Number(b.scoreBreakdown.weighted || 0) - Number(a.scoreBreakdown.weighted || 0));
  }

  function createDashboardPrioritization() {
    return Object.freeze({
      version: VERSION,
      criteria: CRITERIA.slice(),
      scoreBreakdown,
      weightedScore,
      rankCandidates,
    });
  }

  global.JooParkDashboardPrioritization = Object.freeze({
    version: VERSION,
    create: createDashboardPrioritization,
  });
})(typeof window !== "undefined" ? window : globalThis);
