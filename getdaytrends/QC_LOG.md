# QC Log

## 2026-03-17 - Report Profile Content Generation Upgrade

### Scope
- Added `editorial_profile=report` for `long`, `threads`, and `naver_blog`
- Added fact-grounding guardrails to reduce unsupported named entities, stats, and invented examples
- Split Threads quality handling away from short tweet generation
- Expanded QA from `tweets` only to `tweets`, `threads_posts`, `long_posts`, and `blog_posts`
- Changed regeneration flow to rerun only failed content groups once instead of regenerating the whole batch

### Files Checked
- `config.py`
- `generator.py`
- `main.py`
- `.env.example`
- `tests/test_config.py`
- `tests/test_generator.py`
- `tests/test_integration.py`
- `tests/test_quality_diversity.py`

### QC Checks
- Syntax compile check:
  - `python -X utf8 - <<py_compile for config.py/generator.py/main.py/tests>>`
- Targeted verification:
  - `python -X utf8 -m pytest getdaytrends/tests/test_config.py getdaytrends/tests/test_generator.py getdaytrends/tests/test_integration.py -q`
  - Result: `66 passed`
- Regression verification:
  - `python -X utf8 -m pytest getdaytrends/tests/test_quality_diversity.py -q`
  - Result: `34 passed`
- Full project verification:
  - `python -X utf8 -m pytest getdaytrends/tests -q`
  - Result: `270 passed`

### Review Notes
- No blocking issues found in the implemented change set
- Cache reconstruction now restores `naver_blog` items separately instead of mixing them into short tweets
- Report profile affects only `long`, `threads`, `naver_blog`; short tweet prompt behavior remains unchanged
- QA now catches the three target regressions from recent samples:
  - unsupported blog entities/stats
  - Threads hashtags and vote-bait prompts
  - long-form cliche/article-style phrasing

### Residual Risks
- No live LLM smoke run was executed against production credentials, so prompt quality was validated by tests and static review, not by real model output
- Rule-based QA may still miss subtle hallucinations that reuse generic wording without obvious named entities

### Status
- QC passed
- Recorded after implementation and full test suite verification
