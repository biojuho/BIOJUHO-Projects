"""3단계 — 플랫폼별 콘텐츠 생성 + QA 검증."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from collectors.base import llm_analyze
from loguru import logger as log
from prompts.content_generation import (
    CONTENT_GENERATION_SYSTEM,
    build_content_prompt,
)
from storage.models import (
    ContentBatch,
    GeneratedContent,
    MergedTrendReport,
    PersonaFitScore,
    QAAxisDiagnostic,
    QAReport,
    ThreadPost,
    UnifiedChecklist,
)

if TYPE_CHECKING:
    from config import CIEConfig


# ───────────────────────────────────────────────────
#  콘텐츠 생성
# ───────────────────────────────────────────────────


async def generate_platform_content(
    platform: str,
    trend_report: MergedTrendReport,
    checklist: UnifiedChecklist,
    config: CIEConfig,
    *,
    personas: list[dict] | None = None,
) -> list[GeneratedContent]:
    """단일 플랫폼의 콘텐츠를 생성한다."""
    log.info(f"✍️ [3단계] {platform.upper()} 콘텐츠 생성 시작...")

    prompt = build_content_prompt(
        platform=platform,
        project_name=config.project_name,
        core_message=config.project_core_message,
        target_audience=config.target_audience,
        trend_summary=trend_report.to_summary_text(),
        regulation_checklist=checklist.to_checklist_text(),
        personas=personas,
    )

    data = await llm_analyze(
        CONTENT_GENERATION_SYSTEM,
        prompt,
        tier=config.content_generation_tier,
    )

    contents = []
    for item in data.get("contents", []):
        self_check = item.get("self_check", {})

        # X 스레드 thread_posts 파싱
        thread_posts = []
        for tp in item.get("thread_posts", []):
            if isinstance(tp, dict):
                body_text = str(tp.get("body", ""))
                thread_posts.append(ThreadPost(
                    index=int(tp.get("index", len(thread_posts))),
                    role=str(tp.get("role", "body")),
                    body=body_text,
                    char_count=len(body_text),
                ))

        content = GeneratedContent(
            platform=platform,
            content_type=item.get("content_type", "post"),
            title=item.get("title", ""),
            body=item.get("body", ""),
            hashtags=item.get("hashtags", []),
            trend_keywords_used=item.get("trend_keywords_used", []),
            regulation_compliant=self_check.get("regulation_compliant", False),
            algorithm_optimized=self_check.get("algorithm_optimized", False),
            created_at=datetime.now(),
            thread_posts=thread_posts,
        )
        contents.append(content)

    if not contents:
        log.warning(f"  ⚠️ {platform.upper()} LLM이 빈 contents를 반환했습니다")
    else:
        log.info(f"  ✅ {platform.upper()} 콘텐츠 {len(contents)}건 생성 완료")
    return contents


async def generate_all_content(
    trend_report: MergedTrendReport,
    checklist: UnifiedChecklist,
    config: CIEConfig,
) -> ContentBatch:
    """모든 대상 플랫폼의 콘텐츠를 병렬 생성한다."""
    personas = config.load_personas()
    tasks = [generate_platform_content(p, trend_report, checklist, config, personas=personas) for p in config.platforms]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_contents = []
    for platform, result in zip(config.platforms, results):
        if isinstance(result, Exception):
            log.error(f"  ❌ {platform.upper()} 콘텐츠 생성 실패: {result}")
        else:
            all_contents.extend(result)

    batch = ContentBatch(
        contents=all_contents,
        trend_report=trend_report,
        checklist=checklist,
        created_at=datetime.now(),
    )

    log.info(f"📦 전체 콘텐츠 배치: {batch.summary()}")
    return batch


# ───────────────────────────────────────────────────
#  QA 검증 (7축 주요 + 3축 보조)
# ───────────────────────────────────────────────────


def _safe_int(value, cap: int) -> int:
    """LLM 응답의 점수를 안전하게 정수로 변환한다 (0~cap 범위 클램프)."""
    if value is None:
        return 0
    try:
        return max(0, min(int(value), cap))
    except (ValueError, TypeError):
        import re

        match = re.search(r"\d+", str(value))
        return max(0, min(int(match.group()), cap)) if match else 0


QA_SYSTEM = """\
너는 소셜 미디어 콘텐츠 품질 감사관이야.
주어진 콘텐츠를 10가지 축으로 점수를 매기고,
각 축별 진단(이유+개선안)과 페르소나별 적합도를 제공해.
솔직하고 엄격하게 평가해. 점수에 대한 구체적 근거를 반드시 제시해."""

# ── 축별 메타 (파싱 및 진단 생성에 사용) ──
_AXIS_META: list[tuple[str, int, str]] = [
    ("hook", 20, "첫 문장 주목도"),
    ("fact", 15, "사실 일관성"),
    ("tone", 15, "톤 일관성"),
    ("kick", 15, "결론/펀치라인"),
    ("angle", 15, "고유 관점"),
    ("regulation", 10, "규제 준수"),
    ("algorithm", 10, "알고리즘 최적화"),
    ("reader_value", 10, "독자 페인포인트 해소"),
    ("originality", 10, "정보 희소성/독창성"),
    ("credibility", 10, "신뢰 근거 제시"),
]

QA_PRO_PROMPT = """\
■ 평가 대상 콘텐츠
플랫폼: {platform}
유형: {content_type}
본문:
---
{body}
---

■ 트렌드 컨텍스트 요약
{trend_context}

■ 규제 체크리스트
{regulation_checklist}
{persona_context}
■ 평가 기준 (7축 주요 100점 + 3축 보조)
[주요 7축 — 합산 100점]
1. hook (0~20): 첫 문장 주목도. 즉시 관심을 끄는가?
2. fact (0~15): 트렌드 컨텍스트와 일치하는가? 날조된 주장이 없는가?
3. tone (0~15): 플랫폼에 맞는 톤인가? AI티가 나지 않는가?
4. kick (0~15): 마지막 문장이 강한가? 공유를 유도하는가?
5. angle (0~15): 뻔한 요약이 아닌 고유한 관점이 있는가?
6. regulation (0~10): 규제 체크리스트를 모두 준수하는가?
7. algorithm (0~10): 해당 플랫폼 알고리즘 우대 요소를 반영했는가?

[보조 3축 — 독자가치 진단, 합산 미포함]
8. reader_value (0~10): 독자의 실제 문제/페인포인트를 해소하는가?
9. originality (0~10): 이미 알려진 내용의 요약이 아닌 희소한 관점인가?
10. credibility (0~10): 수치·사례·출처 등 신뢰 근거를 제시하는가?

■ 출력 형식 — 반드시 JSON으로:
```json
{{
  "scores": {{
    "hook": 점수, "fact": 점수, "tone": 점수, "kick": 점수, "angle": 점수,
    "regulation": 점수, "algorithm": ���수,
    "reader_value": 점수, "originality": 점수, "credibility": 점수
  }},
  "diagnostics": {{
    "hook": {{"reason": "이 점수의 근거", "suggestion": "구체적 개선안"}},
    "fact": {{"reason": "...", "suggestion": "..."}},
    "tone": {{"reason": "...", "suggestion": "..."}},
    "kick": {{"reason": "...", "suggestion": "..."}},
    "angle": {{"reason": "...", "suggestion": "..."}},
    "regulation": {{"reason": "...", "suggestion": "..."}},
    "algorithm": {{"reason": "...", "suggestion": "..."}},
    "reader_value": {{"reason": "...", "suggestion": "..."}},
    "originality": {{"reason": "...", "suggestion": "..."}},
    "credibility": {{"reason": "...", "suggestion": "..."}}
  }},
  "persona_fits": [{{"persona_id": "id", "fit_score": 0~10, "reason": "적합도 근거"}}],
  "rewrite_suggestion": "이 콘텐츠를 개선하려면 이렇게 바꿔라 (2~3문장)",
  "warnings": ["경고사항"]
}}
```

반드시 JSON만 응답해."""


def _build_persona_qa_context(personas: list[dict] | None) -> str:
    """QA 프롬프트에 주입할 페르소나 컨텍스트를 생성한다."""
    if not personas:
        return ""
    lines = ["\n■ 독자 페르소나 (각 페르소나별 적합도를 persona_fits에 평가)"]
    for p in personas:
        pain = ", ".join(p.get("pain_points", [])[:2])
        lines.append(f"  - {p.get('id', '?')} ({p.get('name', '')}): {pain}")
    return "\n".join(lines) + "\n"


def _parse_pro_qa(data: dict, config) -> QAReport:
    """Pro QA LLM 응답을 QAReport + 진단으로 파싱한다."""
    # scores는 flat 또는 nested 구조 모두 지원
    scores = data.get("scores", data)

    # 축별 점수 추출
    score_map = {}
    for axis, cap, _label in _AXIS_META:
        score_map[axis] = _safe_int(scores.get(axis), cap)

    # 축별 진단 추출
    raw_diag = data.get("diagnostics", {})
    diagnostics = []
    for axis, cap, label in _AXIS_META:
        d = raw_diag.get(axis, {})
        diagnostics.append(QAAxisDiagnostic(
            axis=axis,
            score=score_map[axis],
            max_score=cap,
            reason=str(d.get("reason", "")) if isinstance(d, dict) else "",
            suggestion=str(d.get("suggestion", "")) if isinstance(d, dict) else "",
        ))

    # 페르소나 적합도 추출
    persona_fits = []
    for pf in data.get("persona_fits", []):
        if isinstance(pf, dict):
            persona_fits.append(PersonaFitScore(
                persona_id=str(pf.get("persona_id", "")),
                persona_name=str(pf.get("persona_name", pf.get("persona_id", ""))),
                fit_score=_safe_int(pf.get("fit_score"), 10),
                reason=str(pf.get("reason", "")),
            ))

    return QAReport(
        hook_score=score_map["hook"],
        fact_score=score_map["fact"],
        tone_score=score_map["tone"],
        kick_score=score_map["kick"],
        angle_score=score_map["angle"],
        regulation_score=score_map["regulation"],
        algorithm_score=score_map["algorithm"],
        warnings=data.get("warnings", []),
        reader_value_score=score_map["reader_value"],
        originality_score=score_map["originality"],
        credibility_score=score_map["credibility"],
        applied_min_score=config.qa_min_score,
        diagnostics=diagnostics,
        persona_fits=persona_fits,
        rewrite_suggestion=str(data.get("rewrite_suggestion", "")),
    )


async def validate_content(
    content: GeneratedContent,
    trend_report: MergedTrendReport,
    checklist: UnifiedChecklist,
    config: CIEConfig,
    *,
    personas: list[dict] | None = None,
) -> QAReport:
    """단일 콘텐츠에 대해 10축 Pro QA 검증을 수행한다."""
    prompt = QA_PRO_PROMPT.format(
        platform=content.platform,
        content_type=content.content_type,
        body=content.body[:3000],
        trend_context=trend_report.to_summary_text()[:1500],
        regulation_checklist=checklist.to_checklist_text()[:1500],
        persona_context=_build_persona_qa_context(personas),
    )

    data = await llm_analyze(QA_SYSTEM, prompt, tier=config.qa_tier)
    return _parse_pro_qa(data, config)


async def _validate_and_maybe_regenerate(
    index: int,
    content: GeneratedContent,
    trend_report: MergedTrendReport,
    checklist: UnifiedChecklist,
    config: CIEConfig,
    *,
    personas: list[dict] | None = None,
) -> tuple[int, GeneratedContent]:
    """Pro QA 검증 → 미달 시 진단 피드백 기반 타겟 재생성.

    Basic과의 차이: 재생성 시 실패 원인(약점 축 + 구체적 개선안)을
    프롬프트에 주입하여 LLM이 정확히 무엇을 고쳐야 하는지 안다.

    Returns:
        (index, final_content)
    """
    qa = await validate_content(content, trend_report, checklist, config, personas=personas)
    content.qa_report = qa
    passed = qa.passes(config.qa_min_score)
    emoji = "✅" if passed else "❌"

    # Pro 로깅: 약점 축 + 페르소나 적합도
    log.info(
        f"  {emoji} [{content.platform}/{content.content_type}] "
        f"QA: {qa.total_score}/100 (기준: {config.qa_min_score}) "
        f"{'PASS' if passed else 'FAIL'}"
    )
    if qa.weak_axes:
        weak_names = ", ".join(f"{d.axis}({d.score}/{d.max_score})" for d in qa.weak_axes)
        log.info(f"    약점: {weak_names}")
    if qa.persona_fits:
        fit_str = " | ".join(f"{p.persona_name}:{p.fit_score}" for p in qa.persona_fits)
        log.info(f"    페르소나: {fit_str}")
    if qa.warnings:
        for w in qa.warnings:
            log.warning(f"    ⚠️ {w}")

    # ── 미달 시 진단 기반 타겟 재생성 ──
    if not passed and config.qa_max_retries > 0:
        retry_feedback = qa.to_retry_feedback()
        log.info(f"  🔄 진단 기반 재생성 ({content.platform})...")

        try:
            regen = await _regenerate_with_feedback(
                content.platform, trend_report, checklist, config,
                personas=personas, feedback=retry_feedback,
            )
        except Exception as e:
            log.warning(f"  ⚠️ 재생성 실패 — 원본 유지 ({content.platform}): {e}")
            return index, content

        if not regen:
            log.warning(f"  ⚠️ 재생성 결과 없음 — 원본 유지 ({content.platform})")
            return index, content

        new_content = regen[0]
        new_qa = await validate_content(new_content, trend_report, checklist, config, personas=personas)
        new_content.qa_report = new_qa
        if new_qa.total_score > qa.total_score:
            log.info(f"    ✅ 재생성 개선: {qa.total_score} → {new_qa.total_score}")
            if new_qa.weak_axes:
                still_weak = ", ".join(d.axis for d in new_qa.weak_axes)
                log.info(f"    잔존 약점: {still_weak}")
            return index, new_content
        log.info(f"    ↩️ 원본 유지 (재생성 {new_qa.total_score} ≤ 원본 {qa.total_score})")

    return index, content


async def _regenerate_with_feedback(
    platform: str,
    trend_report: MergedTrendReport,
    checklist: UnifiedChecklist,
    config: CIEConfig,
    *,
    personas: list[dict] | None = None,
    feedback: str = "",
) -> list[GeneratedContent]:
    """진단 피드백을 프롬프트에 주입한 타겟 재생성.

    기존 generate_platform_content와 동일하되, 프롬프트 끝에
    이전 QA 진단 피드백을 추가하여 LLM이 약점을 인지하고 개선한다.
    """
    from prompts.content_generation import (
        CONTENT_GENERATION_SYSTEM,
        build_content_prompt,
    )

    base_prompt = build_content_prompt(
        platform=platform,
        project_name=config.project_name,
        core_message=config.project_core_message,
        target_audience=config.target_audience,
        trend_summary=trend_report.to_summary_text(),
        regulation_checklist=checklist.to_checklist_text(),
        personas=personas,
    )

    # 진단 피드백을 JSON 출력 형식 앞에 삽입
    if feedback:
        injection = f"\n■ 이전 QA 진단 — 아래 약점을 반드시 개선하여 다시 작성해줘:\n{feedback}\n"
        # "■ 출력 형식" 앞에 삽입
        marker = "■ 출력 형식"
        if marker in base_prompt:
            base_prompt = base_prompt.replace(marker, injection + "\n" + marker)
        else:
            base_prompt += "\n" + injection

    data = await llm_analyze(
        CONTENT_GENERATION_SYSTEM,
        base_prompt,
        tier=config.content_generation_tier,
    )

    contents = []
    for item in data.get("contents", []):
        self_check = item.get("self_check", {})
        contents.append(GeneratedContent(
            platform=platform,
            content_type=item.get("content_type", "post"),
            title=item.get("title", ""),
            body=item.get("body", ""),
            hashtags=item.get("hashtags", []),
            trend_keywords_used=item.get("trend_keywords_used", []),
            regulation_compliant=self_check.get("regulation_compliant", False),
            algorithm_optimized=self_check.get("algorithm_optimized", False),
            created_at=datetime.now(),
        ))
    return contents


async def validate_and_regenerate(
    batch: ContentBatch,
    config: CIEConfig,
) -> ContentBatch:
    """배치 내 모든 콘텐츠에 대해 Pro QA 검증 → 진단 기반 재생성 (병렬)."""
    if not config.enable_qa_validation:
        return batch

    trend_report = batch.trend_report
    checklist = batch.checklist
    if not trend_report or not checklist:
        log.warning("  ⚠️ QA 검증 생략: 트렌드/체크리스트 컨텍스트 없음")
        return batch

    log.info(f"🔬 Pro QA 검증 시작 ({len(batch.contents)}건, 병렬)...")

    personas = config.load_personas()
    tasks = [
        _validate_and_maybe_regenerate(i, c, trend_report, checklist, config, personas=personas)
        for i, c in enumerate(batch.contents)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, BaseException):
            log.error(f"  ❌ QA 검증 중 예외: {result}")
            continue
        if not isinstance(result, tuple) or len(result) != 2:
            log.error(f"  ❌ QA 검증 예상 외 반환값: {type(result)}")
            continue
        idx, final_content = result
        batch.contents[idx] = final_content

    passed = sum(1 for c in batch.contents if c.qa_passed)
    total = len(batch.contents)
    log.info(f"🔬 Pro QA 완료: {passed}/{total} PASS")

    return batch
