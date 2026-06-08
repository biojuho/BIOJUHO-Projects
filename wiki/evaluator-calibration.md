---
updated: 2026-06-08T15:42:16+09:00
confidence: high
source_types:
  - web
  - paper
  - book
sources:
  - id: openai_graders
    type: web
    title: OpenAI Graders guide
    url: https://developers.openai.com/api/docs/guides/graders
    checked: 2026-06-08
  - id: openai_eval_best_practices
    type: web
    title: OpenAI Evaluation best practices
    url: https://developers.openai.com/api/docs/guides/evaluation-best-practices
    checked: 2026-06-08
  - id: langfuse_llm_as_judge
    type: web
    title: Langfuse LLM-as-a-Judge
    url: https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge
    checked: 2026-06-08
  - id: langfuse_manual_scores
    type: web
    title: Langfuse Manual Scores via UI
    url: https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-ui
    checked: 2026-06-08
  - id: mt_bench_chatbot_arena
    type: paper
    title: "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"
    authors: Lianmin Zheng et al.
    year: 2023
    arxiv: "2306.05685"
    doi: "10.48550/arXiv.2306.05685"
    url: https://arxiv.org/abs/2306.05685
  - id: g_eval
    type: paper
    title: "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment"
    authors: Yang Liu; Dan Iter; Yichong Xu; Shuohang Wang; Ruochen Xu; Chenguang Zhu
    year: 2023
    arxiv: "2303.16634"
    doi: "10.48550/arXiv.2303.16634"
    url: https://arxiv.org/abs/2303.16634
  - id: inter_rater_reliability_book
    type: book
    title: "Handbook of Inter-Rater Reliability"
    authors: Kilem L. Gwet
    year: 2014
    isbn: "9780970806284"
    url: https://openlibrary.org/books/OL47309171M/Handbook_of_Inter-Rater_Reliability
tags:
  - llm-wiki
  - evals
  - evaluator-calibration
  - llm-as-judge
  - human-labels
---

# Evaluator Calibration

[[evaluation]]에서 LLM-as-judge는 확장성 있는 채점 도구지만, JooPark의 release gate에서는 human label과 rubric agreement를 통과하기 전까지 "자동 검증"이 아니라 "자동 후보 점수"로 취급한다. [[eval-result-lineage]]는 judge output마다 `judge_id`, `judge_model`, `judge_prompt_hash`, `rubric_version`, `score_config_id`, `human_alignment_set`, `pass_threshold`를 남겨야 한다.

## Calibration Contract

| Field | Meaning | Rule |
| --- | --- | --- |
| `judge_id` | evaluator identity | model, prompt, rubric, parser가 바뀌면 새 ID |
| `judge_model` | judge model snapshot | provider alias와 returned model id를 분리 |
| `judge_prompt_hash` | evaluator prompt identity | prompt 변경은 score drift 후보 |
| `rubric_version` | scoring criteria version | score range와 examples를 같이 보관 |
| `score_config_id` | score schema | numeric/categorical/boolean/text 구분 |
| `human_alignment_set` | human-labeled calibration subset | blind review와 adjudication 포함 |
| `judge_human_agreement` | judge vs human agreement | kappa, Spearman, pairwise agreement 중 task에 맞게 선택 |
| `judge_drift` | judge behavior drift | same item replay로 추적 |
| `threshold_drift` | pass/fail threshold drift | release gate threshold 변경 기록 |

## What To Calibrate

- OpenAI evaluation best practices says model graders are cheaper and scalable, but should be validated against human labels before optimizing cost or latency. It also names position and verbosity bias as challenges.
- OpenAI Graders recommends building a model grader eval with high-quality model or human examples and ground-truth grades, then adding edge cases over time. It also warns that a trained model can hack the grader and score well on model grader evals while failing expert human evals.
- Langfuse LLM-as-a-Judge frames the judge prompt as input, output, scoring rubric, and optional reference. Its scores can be numeric, categorical, or boolean; JooPark should not mix these without a `score_config_id`.
- Langfuse Manual Scores via UI supports human annotation on traces, sessions, observations, and experiments, and explicitly positions human baselines as a reference point for benchmarking other scores.

## Bias And Agreement

- MT-Bench/Chatbot Arena reports that strong LLM judges can reach over 80% agreement with human preferences, while also studying position, verbosity, self-enhancement, and reasoning limits. Treat the 80% result as benchmark evidence, not a universal guarantee.
- G-Eval shows better human alignment for NLG evaluation with CoT/form-filling, but also flags possible bias toward LLM-generated text. JooPark should record `position_bias`, `verbosity_bias`, and `self_preference_bias` checks when a judge affects release decisions.
- Inter-rater reliability book metadata is used only to anchor agreement measurement as a mature statistics topic. Do not copy formulas or book text; store the chosen agreement coefficient and interpretation rule in the eval artifact.

## A/B 비교: LLM-as-a-Judge vs Human Review

| 선택지 | 장점 | 단점 | JooPark 판단 |
| --- | --- | --- | --- |
| A. LLM-as-a-Judge | 대량 eval과 빠른 release gate에 적합하고 score reasoning을 남길 수 있음 | judge drift, position/verbosity bias, grader hacking 위험 | human_alignment_set 통과 후 자동 gate로 사용 |
| B. Human review | product policy와 domain nuance에 강하고 judge calibration 기준점이 됨 | 느리고 비싸며 reviewer disagreement가 생김 | calibration set, incident, rubric 변경 승인에 사용 |

## A/B 비교: Single Judge vs Judge Panel

| 선택지 | 장점 | 단점 | JooPark 판단 |
| --- | --- | --- | --- |
| A. Single judge | 비용과 latency가 낮고 score 재현이 단순 | judge_model 하나의 편향에 취약 | low-risk regression 보조 |
| B. Judge panel | model/prompt 편향을 줄이고 disagreement signal을 얻음 | 비용, tie-breaker, aggregation 운영이 필요 | high-stakes release와 safety eval 후보 |

## Release Gate Rule

An LLM judge can block or approve a release only when:

- `human_alignment_set` contains representative pass, fail, and edge cases.
- At least two human reviewers or one reviewer plus adjudication produce a trusted baseline.
- `judge_human_agreement` and `pairwise_agreement` meet the configured threshold.
- Bias probes for position and verbosity are recorded.
- The judge prompt, rubric, model, and parser are versioned and replayable.
- [[eval-result-lineage]] has `lineage_complete=true` for the calibration run.

## Backlinks

- [[index]]
- [[evaluation]]
- [[eval-result-lineage]]
- [[eval-dataset-governance]]
- [[eval-failure-triage]]
- [[postmortem-action-ledger]]
- [[rollout-decision-log]]
- [[source-governance]]

## References

### Web

- OpenAI, Graders guide, checked 2026-06-08: https://developers.openai.com/api/docs/guides/graders
- OpenAI, Evaluation best practices, checked 2026-06-08: https://developers.openai.com/api/docs/guides/evaluation-best-practices
- Langfuse, LLM-as-a-Judge, checked 2026-06-08: https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge
- Langfuse, Manual Scores via UI, checked 2026-06-08: https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-ui

### Paper

- Zheng, L. et al. (2023). "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." arXiv:2306.05685. DOI: 10.48550/arXiv.2306.05685. https://arxiv.org/abs/2306.05685
- Liu, Y.; Iter, D.; Xu, Y.; Wang, S.; Xu, R.; Zhu, C. (2023). "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment." arXiv:2303.16634. DOI: 10.48550/arXiv.2303.16634. https://arxiv.org/abs/2303.16634

### Book

- Gwet, K. L. (2014). "Handbook of Inter-Rater Reliability." Advanced Analytics, LLC. ISBN 9780970806284. Open Library: https://openlibrary.org/books/OL47309171M/Handbook_of_Inter-Rater_Reliability
