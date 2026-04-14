# GetDayTrends Content Quality Improvement Plan (2026-04-14)

Checkpoint recorded after the runtime-hardening pass was validated and the remaining issues were narrowed down to content-quality warnings rather than pipeline stability failures.

## Status

- Overall runtime status: PASS
- Quality status: WARNING
- Scope: `automation/getdaytrends` generation QA, fact-check, diversity gate
- Date verified: 2026-04-14
- Trigger run: `python .\getdaytrends\main.py --one-shot --dry-run --no-alerts --limit 1`
- Trigger result: exit code `0`, but repeated QA / FactCheck / diversity warnings remained

## What Is Still Failing

### 1. QA retries are not reason-aware

- The QA path re-runs failed groups in [pipeline_steps.py](</d:/AI project/automation/getdaytrends/core/pipeline_steps.py:274>).
- However, the retry call only passes group names into `regenerate_content_groups(...)`.
- The specific failure reasons from [content_qa.py](</d:/AI project/automation/getdaytrends/content_qa.py:220>) such as:
  - regulation score too low
  - fact violation
  - banned phrasing / AI-toned wording
- are not fed back into the regeneration prompt.
- Result: the second pass can reproduce the same class of defect even when the total score improves.

### 2. QA logs hide the real failure dimension

- The warning summary in [pipeline_steps.py](</d:/AI project/automation/getdaytrends/core/pipeline_steps.py:293>) only emphasizes `total/threshold`.
- But the actual fail condition in [content_qa.py](</d:/AI project/automation/getdaytrends/content_qa.py:220>) is broader:
  - `total < threshold`
  - `regulation <= 3`
  - `fact_violation`
- Result: triage is slower because a group can show `77/50` and still fail, but the warning line does not make that obvious.

### 3. Fact-check retries are too coarse

- The fact-check path in [pipeline_steps.py](</d:/AI project/automation/getdaytrends/core/pipeline_steps.py:331>) regenerates whole groups when hallucinations are detected.
- The checker in [fact_checker.py](</d:/AI project/automation/getdaytrends/fact_checker.py:578>) evaluates one combined string per group.
- Claim-level failure details are not turned into prompt guidance for regeneration.
- Result: retries are expensive and broad, while the prompt still lacks a focused “remove or ground these claims” instruction.

### 4. Diversity QA only warns

- The diversity gate in [pipeline_steps.py](</d:/AI project/automation/getdaytrends/core/pipeline_steps.py:451>) embeds the generated tweets and logs pairs above cosine similarity `0.88`.
- It appends a warning to `run.errors`, but it does not trigger targeted rewrites.
- Result: the run finishes successfully, but the output set can still contain near-duplicate tweet variants.

### 5. Schema-light prediction fallback is quieter, but still mostly passive

- The prediction feature extractor now treats optional missing columns like `run_date` and `cross_source_confidence` as expected skips in [features.py](</d:/AI project/packages/shared/prediction/features.py:214>).
- That removed warning noise, but it does not yet improve the prediction inputs themselves.
- Result: operational logs are cleaner, but prediction quality still depends on sparse local evidence.

## Recommended Workstreams

### Workstream A. Reason-aware QA regeneration

**Goal**

- Make the retry prompt explicitly correct the reason the first pass failed.

**Changes**

- Extend `regenerate_content_groups(...)` to accept a structured feedback payload, not just group names.
- Pass per-group `issues`, `reason`, `worst`, `regulation`, and `fact_violation` from `audit_generated_content(...)`.
- Update the prompt builder / generator path so retries say things like:
  - avoid article-style openings
  - remove AI-register polite phrasing
  - avoid unsupported proper nouns
  - keep the same factual scope as source context

**Primary files**

- [pipeline_steps.py](</d:/AI project/automation/getdaytrends/core/pipeline_steps.py:274>)
- [content_qa.py](</d:/AI project/automation/getdaytrends/content_qa.py:292>)
- [generator.py](</d:/AI project/automation/getdaytrends/generator.py:561>)
- [prompt_builder.py](</d:/AI project/automation/getdaytrends/prompt_builder.py:138>)

### Workstream B. Claim-aware fact-check regeneration

**Goal**

- Regenerate only after telling the model which claims failed and what evidence is allowed.

**Changes**

- Add a compact fact-check feedback object per group:
  - failed claims
  - unverifiable claims
  - hallucinated claims
  - allowed evidence snippets from `trend.context`
- Thread that feedback into the regeneration prompt.
- Keep whole-group regeneration for now, but make it evidence-constrained.
- Consider a rule: if source evidence is too sparse, mark the group as “needs softer claim wording” instead of repeatedly forcing hard factual assertions.

**Primary files**

- [pipeline_steps.py](</d:/AI project/automation/getdaytrends/core/pipeline_steps.py:331>)
- [fact_checker.py](</d:/AI project/automation/getdaytrends/fact_checker.py:578>)
- [generator.py](</d:/AI project/automation/getdaytrends/generator.py:561>)

### Workstream C. Enforced diversity rewrite

**Goal**

- Turn diversity warnings into a corrective action instead of a passive log.

**Changes**

- Use `config.diversity_sim_threshold` consistently in `_run_diversity_qa(...)` instead of the current hard-coded `0.88`.
- Identify the most-duplicated tweet variants.
- Regenerate only the duplicated variants with explicit constraints:
  - new hook shape
  - different emotional stance
  - different sentence rhythm
  - preserve facts, change framing
- Keep the warning log, but add a targeted rewrite pass before save.

**Primary files**

- [pipeline_steps.py](</d:/AI project/automation/getdaytrends/core/pipeline_steps.py:451>)
- [config.py](</d:/AI project/automation/getdaytrends/config.py:310>)
- [generator.py](</d:/AI project/automation/getdaytrends/generator.py:198>)

### Workstream D. Better quality telemetry

**Goal**

- Make the next QC pass faster and more objective.

**Changes**

- Log the real QA fail reason beside `total/threshold`.
- Store per-group retry metadata in `batch.metadata`:
  - first-pass QA scores
  - second-pass QA scores
  - fact-check summary
  - diversity collisions
- Add regression fixtures for:
  - article-style first sentence
  - AI-register polite phrasing
  - unsupported proper noun insertion
  - near-duplicate tweet variants

**Primary files**

- [pipeline_steps.py](</d:/AI project/automation/getdaytrends/core/pipeline_steps.py:376>)
- [test_edape.py](</d:/AI project/automation/getdaytrends/edape/tests/test_edape.py:205>)
- [test_generator.py](</d:/AI project/automation/getdaytrends/tests/test_generator.py:350>)
- [test_fact_checker.py](</d:/AI project/automation/getdaytrends/tests/test_fact_checker.py:317>)

## Recommended Execution Order

1. Workstream D first
- Improve logs and metadata so follow-up tuning is measurable.

2. Workstream A second
- QA retry quality will likely yield the fastest visible improvement.

3. Workstream B third
- Fact-check retries need better evidence threading once retry prompts can accept structured feedback.

4. Workstream C fourth
- Diversity rewrite should come after retry prompts can intentionally change framing.

## Acceptance Criteria

### Phase 1 acceptance

- `python .\getdaytrends\main.py --one-shot --dry-run --no-alerts --limit 1` still exits `0`
- QA warnings include the real failure dimension, not just `total/threshold`
- retry prompts receive structured QA and fact-check feedback

### Phase 2 acceptance

- repeated second-pass QA failures for the same reason are reduced on representative fixtures
- hallucination-triggered retries include claim/evidence feedback
- optional schema-light prediction fallbacks stay at `info` level only

### Phase 3 acceptance

- no diversity warning on a representative 1-trend dry-run
- tweet variants over the configured similarity threshold are rewritten before save
- QC output clearly separates runtime issues from content-quality issues

## Suggested Next Session Scope

- Keep the next slice narrow:
  - telemetry + reason-aware QA retry first
- Do not mix this with unrelated infra or scheduler work.
- Reuse the successful 2026-04-14 dry-run command as the baseline verification command.
