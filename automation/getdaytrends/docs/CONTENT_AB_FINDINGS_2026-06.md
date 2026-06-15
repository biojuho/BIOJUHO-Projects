# Content A/B findings — 2026-06

Evidence record for the content-quality A/B cycle (AutoResearch loop). Keeps
rejected hypotheses from being re-tried and documents the current optimization
state. All runs used the deterministic `content_qa._audit_content_group` scorer
(no LLM cost beyond generation); total generation spend ≈ $0.06.

Harness: `scripts/ab_test_content_variants.py` (run_ab + failure-driver
classification), `scripts/ab_test_hook_research.py` (hook hypothesis).

## Adopted (variant beat baseline or fixed a real defect)

| Change | Evidence | Commit |
| --- | --- | --- |
| Tweet prompt 160–240 char floor | eliminated `160자 미만` warnings | 97e4a49 |
| Grounding instruction (only context-present specifics) | failed batches 6/6 → 5/6 across two runs, avg_b 66→69 | b0e1c12 |
| Fact-checker false-positive fixes (common words / casual counts / digit-leading quantities) | token-level false flags removed, full suite green | 7b00682, 7af3a25, 681d121 |

## Rejected (did not beat baseline — NOT adopted)

| Hypothesis | Result | Why rejected |
| --- | --- | --- |
| Tone variant B (blunt/argumentative) | n=9: wins 5-5, avg 63.78 vs 65.11 (noise), both fail 100% | tied wins, margin within noise, B fails every batch |
| Research-backed hook block (curiosity/contrarian/question/problem hooks) | n=2: baseline avg 77.0 vs 69.0, baseline wins 2-1 | did not beat the current prompt on measured quality |

## Structural finding (not a bug)

Batch `fact_violation` stays ~100% even after the false-positive fixes. The
residual is the fact auditor correctly flagging genuinely unverifiable specifics
the LLM invents (e.g. foreign-holiday dates, made-up prices) against sparse
trend context. Each failure forces one regeneration. The real levers are
**richer context grounding at collection time** or accepting the regeneration
cost — both larger product decisions, not prompt tweaks.

## Conclusion

The current production prompt is near a local optimum for the deterministic
scorer: only the grounding alignment helped; tone and hook rewrites did not.
Further measurable gains need **real engagement labels** (the measured-metrics
pipeline in `scripts/refresh_tweet_metrics.py` once tweets are published with
metrics) rather than more proxy-scored prompt variants.
