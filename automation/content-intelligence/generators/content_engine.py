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
    QAReport,
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
    )

    data = await llm_analyze(
        CONTENT_GENERATION_SYSTEM,
        prompt,
        tier=config.content_generation_tier,
    )

    contents = []
    for item in data.get("contents", []):
        self_check = item.get("self_check", {})
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
        )
        contents.append(content)

    log.info(f"  ✅ {platform.upper()} 콘텐츠 {len(contents)}건 생성 완료")
    return contents


async def generate_all_content(
    trend_report: MergedTrendReport,
    checklist: UnifiedChecklist,
    config: CIEConfig,
) -> ContentBatch:
    """모든 대상 플랫폼의 콘텐츠를 병렬 생성한다."""
    tasks = [generate_platform_content(p, trend_report, checklist, config) for p in config.platforms]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    all_contents = []
    for platform_contents in results:
        if isinstance(platform_contents, list):
            all_contents.extend(platform_contents)

    batch = ContentBatch(
        contents=all_contents,
        trend_report=trend_report,
        checklist=checklist,
        created_at=datetime.now(),
    )

    log.info(f"📦 전체 콘텐츠 배치: {batch.summary()}")
    return batch


# ───────────────────────────────────────────────────
#  QA 검증 (7축)
# ───────────────────────────────────────────────────

QA_SYSTEM = """\
너는 소셜 미디어 콘텐츠 품질 감사관이야.
주어진 콘텐츠를 7가지 축으로 점수를 매기고, 구체적인 경고사항을 제시해.
솔직하고 엄격하게 평가해."""

QA_PROMPT_TEMPLATE = """\
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

■ 평가 기준 (7축)
1. hook (0~20): 첫 문장 주목도. 즉시 관심을 끄는가?
2. fact (0~15): 트렌드 컨텍스트와 일치하는가? 날조된 주장이 없는가?
3. tone (0~15): 플랫폼에 맞는 톤인가? AI티가 나지 않는가?
4. kick (0~15): 마지막 문장이 강한가? 공유를 유도하는가?
5. angle (0~15): 뻔한 요약이 아닌 고유한 관점이 있는가?
6. regulation (0~10): 규제 체크리스트를 모두 준수하는가?
7. algorithm (0~10): 해당 플랫폼 알고리즘 우대 요소를 반영했는가?

■ 출력 형식 — 반드시 JSON으로:
```json
{{
  "hook": 점수, "fact": 점수, "tone": 점수,
  "kick": 점수, "angle": 점수,
  "regulation": 점수, "algorithm": 점수,
  "warnings": ["경고사항1", "경고사항2"]
}}
```

반드시 JSON만 응답해."""


async def validate_content(
    content: GeneratedContent,
    trend_report: MergedTrendReport,
    checklist: UnifiedChecklist,
    config: CIEConfig,
) -> QAReport:
    """단일 콘텐츠에 대해 7축 QA 검증을 수행한다."""
    prompt = QA_PROMPT_TEMPLATE.format(
        platform=content.platform,
        content_type=content.content_type,
        body=content.body[:3000],
        trend_context=trend_report.to_summary_text()[:1500],
        regulation_checklist=checklist.to_checklist_text()[:1500],
    )

    data = await llm_analyze(QA_SYSTEM, prompt, tier=config.qa_tier)

    return QAReport(
        hook_score=min(int(data.get("hook", 0)), 20),
        fact_score=min(int(data.get("fact", 0)), 15),
        tone_score=min(int(data.get("tone", 0)), 15),
        kick_score=min(int(data.get("kick", 0)), 15),
        angle_score=min(int(data.get("angle", 0)), 15),
        regulation_score=min(int(data.get("regulation", 0)), 10),
        algorithm_score=min(int(data.get("algorithm", 0)), 10),
        warnings=data.get("warnings", []),
    )


async def validate_and_regenerate(
    batch: ContentBatch,
    config: CIEConfig,
) -> ContentBatch:
    """배치 내 모든 콘텐츠에 대해 QA 검증 → 미달 시 재생성."""
    if not config.enable_qa_validation:
        return batch

    trend_report = batch.trend_report
    checklist = batch.checklist
    if not trend_report or not checklist:
        log.warning("  ⚠️ QA 검증 생략: 트렌드/체크리스트 컨텍스트 없음")
        return batch

    log.info(f"🔬 QA 검증 시작 ({len(batch.contents)}건)...")

    for i, content in enumerate(batch.contents):
        qa = await validate_content(content, trend_report, checklist, config)
        content.qa_report = qa
        emoji = "✅" if qa.pass_threshold else "❌"
        log.info(
            f"  {emoji} [{content.platform}/{content.content_type}] "
            f"QA: {qa.total_score}/100 "
            f"{'PASS' if qa.pass_threshold else 'FAIL'}"
        )
        if qa.warnings:
            for w in qa.warnings:
                log.warning(f"    ⚠️ {w}")

        # 미달 시 1회 재생성
        if not qa.pass_threshold and config.qa_max_retries > 0:
            log.info(f"  🔄 재생성 시도 ({content.platform})...")
            regen = await generate_platform_content(content.platform, trend_report, checklist, config)
            if regen:
                new_content = regen[0]
                new_qa = await validate_content(new_content, trend_report, checklist, config)
                new_content.qa_report = new_qa
                if new_qa.total_score > qa.total_score:
                    batch.contents[i] = new_content
                    log.info(f"    ✅ 재생성 개선: " f"{qa.total_score} → {new_qa.total_score}")
                else:
                    log.info("    ↩️ 원본 유지 (재생성이 더 낮음)")

    passed = sum(1 for c in batch.contents if c.qa_passed)
    total = len(batch.contents)
    log.info(f"🔬 QA 완료: {passed}/{total} PASS")

    return batch
