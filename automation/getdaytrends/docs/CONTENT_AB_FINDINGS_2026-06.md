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
| Ending-variation block (cap 음/임 endings, vary the rest) | n=3: baseline avg 67.67 vs 69.0, baseline wins 2-1 | marginal avg edge but loses per-trend; not a clear win |

Three distinct prompt-enhancement hypotheses (tone, hook, endings) all failed to
beat the baseline → the production prompt is at a local optimum for the
deterministic scorer. `scripts/ab_test_hook_research.py --variant {hook,endings}`
is the reusable harness for future hypotheses.

## Structural finding (not a bug)

Batch `fact_violation` stays ~100% even after the false-positive fixes. The
residual is the fact auditor correctly flagging genuinely unverifiable specifics
the LLM invents (e.g. foreign-holiday dates, made-up prices) against sparse
trend context. Each failure forces one regeneration. The real levers are
**richer context grounding at collection time** or accepting the regeneration
cost — both larger product decisions, not prompt tweaks.

## Validity caveat (re-run after key rotation)

These A/B runs happened while the Google/Gemini key was leaked (403), so the
LIGHTWEIGHT/MEDIUM tiers were down and generation survived via fallback/HEAVY
paths — i.e. not the intended routing. The "prompt is optimal" conclusion holds
for the deterministic + LLM-judge signals **observed on a degraded stack**.
Re-run the four hypotheses with `scripts/ab_test_hook_research.py --variant ...`
and `scripts/ab_judge_content.py` once the key is rotated (verify with
`scripts/check_llm_keys.py`) before treating the rejections as final.

## Conclusion

The current production prompt is near a local optimum for the deterministic
scorer: only the grounding alignment helped; tone and hook rewrites did not.
Further measurable gains need **real engagement labels** (the measured-metrics
pipeline in `scripts/refresh_tweet_metrics.py` once tweets are published with
metrics) rather than more proxy-scored prompt variants.
