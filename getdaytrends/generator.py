"""
getdaytrends v4.1 - Tweet & Thread & Long-form & Threads Generation
컨텍스트 기반 트윗 3종 + X Premium+ 장문 + Meta Threads 3종 + 강화 쓰레드 3개.
async/await 기반 병렬 생성 + JSON structured output 지원.

v4.1 변경 (프롬프트 고도화):
- Few-shot 예시 추가: 좋은 글/나쁜 글 대비로 LLM 방향 유도
- 훅(첫 문장) 패턴 라이브러리: 6가지 시작 방식 (숫자충격/체감환산/반전선언/내부자/대조/질문)
- 킥(마무리) 패턴 라이브러리: 5가지 마무리 방식 (뒤통수/자조/질문/선언/반전)
- 앵글 분화 강화: 5개 트윗 각도별 구체적 예시 + 시작 방식 교차 강제
- 금지 패턴 확장: 설명체/간접인용/상투구 추가
- 핵심 마인드셋: 정보 30% + 해석 70% 비율 명시
- 장문/Threads 프롬프트 동일 수준 고도화
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Coroutine


from config import AppConfig
from models import GeneratedThread, GeneratedTweet, ScoredTrend, TrendContext, TweetBatch
from shared.llm import LLMClient, TaskTier
from shared.llm.models import LLMPolicy
from utils import run_async, sanitize_keyword

from loguru import logger as log

# [Phase 1] Instructor 구조화된 출력 (선택 의존성)
try:
    from structured_output import (
        TweetGenerationResponse,
        TweetItem,
        extract_structured,
        INSTRUCTOR_AVAILABLE as _INST_OK,
    )
except ImportError:
    _INST_OK = False

_JSON_POLICY = LLMPolicy(response_mode="json")
_PY314_SERIAL_GENERATION = sys.version_info >= (3, 14)


# -- prompt builder import --
from prompt_builder import (  # noqa: F401
    _LANG_NAME_MAP,
    _REPORT_BLOG_SYSTEM,
    _build_account_identity_section,
    _build_available_facts_section,
    _build_category_tone_hint,
    _build_context_section,
    _build_deep_why_section,
    _build_diversity_section,
    _build_fact_guardrail_section,
    _build_golden_reference_section,
    _build_pattern_weights_section,
    _build_scoring_section,
    _parse_json,
    _resolve_language,
    _select_generation_tier,
    _system_long_form,
    _system_thread,
    _system_threads,
    _system_tweets,
    _system_tweets_and_threads,
    _use_report_profile,
)

# ══════════════════════════════════════════════════════
#  0) MARL 강화 트윗 생성 (v16.0)
# ══════════════════════════════════════════════════════

def _should_use_marl(trend: ScoredTrend, config: AppConfig) -> bool:
    """MARL 적용 여부 판정. 비용 관리를 위해 조건부 적용."""
    if not getattr(config, "enable_marl_generation", False):
        return False
    if trend.viral_potential < getattr(config, "marl_min_viral_score", 80):
        return False
    category = getattr(trend, "category", "") or ""
    if not category:
        return True  # 카테고리 미분류 → 기본 적용
    return any(hc in category for hc in config.heavy_categories)


async def generate_tweets_with_marl_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None = None,
    golden_refs: list | None = None,
    pattern_weights: dict | None = None,
) -> "TweetBatch | None":
    """[v16.0] MARL 강화 트윗 생성 — high-value 트렌드 전용.

    생성→자가비평→수정 3단계 파이프라인으로 AI 어투를 줄이고
    분석 깊이를 높인 트윗 생성. MARL 실패 시 기존 방식 폴백.
    """
    from shared.llm.marl import MARLPipeline, MARLConfig

    if not _should_use_marl(trend, config):
        return await generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights)

    from datetime import datetime as _dt
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    identity_section = _build_account_identity_section(config)
    diversity_section = _build_diversity_section(recent_tweets or [])
    category_hint = _build_category_tone_hint(trend)
    deep_why_section = _build_deep_why_section(trend)
    golden_ref_section = _build_golden_reference_section(golden_refs)
    pattern_weights_section = _build_pattern_weights_section(pattern_weights)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{identity_section}{deep_why_section}{context_section}{scoring_section}"
        f"{category_hint}{pattern_weights_section}{golden_ref_section}{diversity_section}\n"
        "위 배경과 컨텍스트를 깊이 소화한 뒤, 쟁점을 추출하고 각 쟁점별로 날카로운 각도의 트윗 작성.\n"
        "중요: 너는 뉴스를 '전달'하는 사람이 아니라 뉴스를 보고 '한마디 하는' 사람임.\n"
        "정보 전달 30% + 너의 해석/시각 70% 비율로 작성.\n"
        "컨텍스트의 구체적 수치/사건/반응을 반드시 활용하되, 그걸 '내 관점'으로 재해석할 것.\n"
        "5개 트윗의 첫 문장이 전부 다른 방식으로 시작해야 함.\n"
        "반드시 JSON만 출력."
    )

    try:
        marl_stages = getattr(config, "marl_stages", 3)
        marl = MARLPipeline(client)
        marl_config = MARLConfig(
            stages=marl_stages,
            generation_tier=TaskTier.LIGHTWEIGHT,
            critique_tier=TaskTier.LIGHTWEIGHT,
            max_tokens_per_stage=1500,
        )

        result = await marl.arun(
            messages=[{"role": "user", "content": user_message}],
            system=_system_tweets(config.tone),
            config=marl_config,
        )
        data = _parse_json(result.final_text)

        if not data:
            log.warning(
                f"[MARL] '{trend.keyword}' JSON 파싱 실패 → 기존 방식 폴백"
            )
            return await generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights)

        tweets = []
        for t in data.get("tweets", []):
            content = t.get("content", "")
            if len(content) > 280:
                content = content[:277] + "..."
                log.warning(f"[MARL] 트윗 280자 초과 트리밍: {trend.keyword}")
            tweets.append(GeneratedTweet(
                tweet_type=t.get("type", ""),
                content=content,
                content_type="short",
                best_posting_time=t.get("best_posting_time", ""),
                expected_engagement=t.get("expected_engagement", ""),
                reasoning=t.get("reasoning", ""),
            ))

        log.info(
            f"[MARL] 트윗 생성 완료: '{trend.keyword}' "
            f"({len(tweets)}개, stages={result.stages_completed})"
        )
        return TweetBatch(
            topic=data.get("topic", trend.keyword),
            tweets=tweets,
            viral_score=trend.viral_potential,
        )

    except Exception as e:
        log.warning(f"[MARL] 생성 실패 '{trend.keyword}': {e} → 기존 방식 폴백")
        return await generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights)


# ══════════════════════════════════════════════════════
#  1) 단문 트윗 5종 (280자) — Haiku tier
# ══════════════════════════════════════════════════════

async def generate_tweets_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None = None,
    golden_refs: list | None = None,
    pattern_weights: dict | None = None,
) -> TweetBatch | None:
    """5종 단문 트윗 비동기 생성 (Haiku — 비용 절감).
    [v9.0] recent_tweets: 이전 생성 내용 주입으로 표현 다양성 보장.
    [v5.0] golden_refs: 골든 레퍼런스 벤치마크 (E. Benchmark QA).
    [v5.0] pattern_weights: 훅/킥 성과 가중치 (B. Adaptive Voice).
    """
    from datetime import datetime as _dt
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    identity_section = _build_account_identity_section(config)
    diversity_section = _build_diversity_section(recent_tweets or [])
    category_hint = _build_category_tone_hint(trend)
    deep_why_section = _build_deep_why_section(trend)
    golden_ref_section = _build_golden_reference_section(golden_refs)
    pattern_weights_section = _build_pattern_weights_section(pattern_weights)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{identity_section}{deep_why_section}{context_section}{scoring_section}"
        f"{category_hint}{pattern_weights_section}{golden_ref_section}{diversity_section}\n"
        "위 배경과 컨텍스트를 깊이 소화한 뒤, 쟁점을 추출하고 각 쟁점별로 날카로운 각도의 트윗 작성.\n"
        "중요: 너는 뉴스를 '전달'하는 사람이 아니라 뉴스를 보고 '한마디 하는' 사람임.\n"
        "정보 전달 30% + 너의 해석/시각 70% 비율로 작성.\n"
        "컨텍스트의 구체적 수치/사건/반응을 반드시 활용하되, 그걸 '내 관점'으로 재해석할 것.\n"
        "5개 트윗의 첫 문장이 전부 다른 방식으로 시작해야 함.\n"
        "반드시 JSON만 출력."
    )

    # [Phase 1] Instructor 우선 시도 → 실패 시 기존 JSON 파싱 폴백
    data = None
    if _INST_OK:
        try:
            full_prompt = f"[시스템]\n{_system_tweets(config.tone)}\n\n[사용자]\n{user_message}"
            inst_result = await extract_structured(
                full_prompt, TweetGenerationResponse,
                tier="lightweight", max_tokens=1500,
            )
            if inst_result and inst_result.tweets:
                data = inst_result.model_dump()
                log.info(f"[Instructor] 트윗 생성 파싱 성공: '{trend.keyword}'")
        except Exception as e:
            log.debug(f"[Instructor] 트윗 생성 폴백: {e}")

    if data is None:
        try:
            response = await client.acreate(
                tier=TaskTier.LIGHTWEIGHT,
                max_tokens=1500,
                policy=_JSON_POLICY,
                system=_system_tweets(config.tone),
                messages=[{"role": "user", "content": user_message}],
            )
            data = _parse_json(response.text)
        except Exception as e:
            log.error(f"트윗 생성 실패 ({trend.keyword}): {e}")
            return None

    if not data:
        log.error(f"트윗 생성 JSON 파싱 실패: {trend.keyword}")
        return None

    tweets = []
    for t in data.get("tweets", []):
        content = t.get("content", "")
        if len(content) > 280:
            content = content[:277] + "..."
            log.warning(f"트윗 280자 초과 트리밍: {trend.keyword} [{t.get('type', '')}]")
        tweets.append(GeneratedTweet(
            tweet_type=t.get("type", ""),
            content=content,
            content_type="short",
            best_posting_time=t.get("best_posting_time", ""),
            expected_engagement=t.get("expected_engagement", ""),
            reasoning=t.get("reasoning", ""),
        ))

    log.info(f"트윗 생성 완료: '{trend.keyword}' ({len(tweets)}개)")
    return TweetBatch(
        topic=data.get("topic", trend.keyword),
        tweets=tweets,
        viral_score=trend.viral_potential,
    )


# ══════════════════════════════════════════════════════
#  2) X Premium+ 장문 포스트 (1,500~3,000자) — Sonnet tier
# ══════════════════════════════════════════════════════

async def generate_long_form_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    tier: TaskTier = TaskTier.LIGHTWEIGHT,  # [v13.0] HEAVY→LIGHTWEIGHT 비용 절감
) -> list[GeneratedTweet]:
    """X Premium+ 장문 콘텐츠 2종 비동기 생성 (v13.0: LIGHTWEIGHT 기본)."""
    from datetime import datetime as _dt
    report_profile = _use_report_profile(config)
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    deep_why_section = _build_deep_why_section(trend)
    fact_guardrail_section = _build_fact_guardrail_section(trend)
    identity_section = _build_account_identity_section(config, include_tone=not report_profile)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{identity_section}{fact_guardrail_section}{deep_why_section}{context_section}{scoring_section}\n"
        "위 '왜 지금 트렌드인가' 배경과 데이터/수치/반응을 깊이 소화한 뒤,\n"
        "읽는 사람이 '이건 저장해야 돼' 하는 장문 2종을 작성.\n"
        "핵심: 뉴스 요약 아님. 이 현상의 이면을 파고드는 분석과 해석.\n"
        "컨텍스트의 구체적 수치/사건/시점 정보를 반드시 활용할 것.\n"
        + (
            "1) 딥다이브 분석 (1,500~3,000자): 남들이 놓친 포인트 기반 분석\n"
            "2) 리포트 코멘트 (1,000~2,000자): 과장 없이 의미와 관찰 포인트 정리\n\n"
            if report_profile
            else
            "1) 딥다이브 분석 (1,500~3,000자): 남들이 놓친 포인트 기반 분석\n"
            "2) 핫테이크 오피니언 (1,000~2,000자): 불편한 소신 + 팩트 근거\n\n"
        )
        + "반드시 JSON만 출력하세요."
    )

    try:
        response = await client.acreate(
            tier=tier,
            max_tokens=4000,
            policy=_JSON_POLICY,
            system=_system_long_form(config.tone, config.editorial_profile),
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json(response.text)

        if not data:
            log.warning(f"장문 생성 JSON 파싱 실패: {trend.keyword}")
            return []

        posts = [
            GeneratedTweet(
                tweet_type=p.get("type", "장문"),
                content=p.get("content", ""),
                content_type="long",
            )
            for p in data.get("posts", [])
        ]

        log.info(f"장문 생성 완료: '{trend.keyword}' ({len(posts)}개, 총 {sum(p.char_count for p in posts)}자)")
        return posts

    except Exception as e:
        log.error(f"장문 생성 실패 ({trend.keyword}): {e}")
        return []


# ══════════════════════════════════════════════════════
#  3) Meta Threads 콘텐츠 (500자) — Haiku tier
# ══════════════════════════════════════════════════════

async def generate_threads_content_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
) -> list[GeneratedTweet]:
    """Meta Threads 최적화 콘텐츠 비동기 생성 (Haiku — 단문)."""
    from datetime import datetime as _dt
    report_profile = _use_report_profile(config)
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    deep_why_section = _build_deep_why_section(trend)
    fact_guardrail_section = _build_fact_guardrail_section(trend)
    identity_section = _build_account_identity_section(config, include_tone=not report_profile)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{identity_section}{fact_guardrail_section}{deep_why_section}{context_section}{scoring_section}\n"
        + (
            "위 배경과 컨텍스트를 소화한 뒤, Threads용 리포트형 포스트 2개를 작성.\n"
            "핵심: 뉴스 전달이 아니라 '이 현상에 대한 내 해석'.\n"
            "컨텍스트의 구체적 수치/사건을 반드시 활용할 것.\n"
            "1) 핵심 브리프: 지금 중요한 사실과 의미를 간결하게 정리\n"
            "2) 쟁점 질문: 팩트를 짚은 뒤 생각할 질문 하나만 남기기\n\n"
            if report_profile
            else
            "위 배경과 컨텍스트를 소화한 뒤, Threads에서 '친구한테 공유' 하고 싶은 글 작성.\n"
            "핵심: 뉴스 전달이 아니라 '이 현상에 대한 내 해석'.\n"
            "컨텍스트의 구체적 수치/사건을 반드시 활용할 것.\n"
            "1) 훅 포스트: 구체적 팩트/숫자로 스크롤 멈추게\n"
            "2) 참여형 포스트: 공감 스토리 + 양자택일 질문\n\n"
        )
        + "각 포스트 500자 이내. 반드시 JSON만 출력하세요."
    )

    try:
        response = await client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=1200,
            policy=_JSON_POLICY,
            system=_system_threads(config.tone, config.editorial_profile),
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json(response.text)

        if not data:
            log.warning(f"Threads 생성 JSON 파싱 실패: {trend.keyword}")
            return []

        posts = [
            GeneratedTweet(
                tweet_type=p.get("type", "Threads"),
                content=p.get("content", ""),
                content_type="threads",
            )
            for p in data.get("posts", [])
        ]

        log.info(f"Threads 생성 완료: '{trend.keyword}' ({len(posts)}개)")
        return posts

    except Exception as e:
        log.error(f"Threads 생성 실패 ({trend.keyword}): {e}")
        return []


# ══════════════════════════════════════════════════════
#  3.5) 네이버 블로그 글감 (2,000~5,000자) — SEO 최적화
# ══════════════════════════════════════════════════════

_BLOG_SYSTEM_JOONGYEON = """당신은 네이버 블로그 전문 콘텐츠 작가입니다.

[정체성]
- AI·테크·트렌드 분야의 전문 블로거
- 복잡한 기술 트렌드를 일반인도 이해할 수 있게 풀어쓰는 능력
- 깊이 있는 분석과 실용적 인사이트를 균형있게 제공

[네이버 블로그 글쓰기 원칙]
1. 구조: 서론(후킹) → 본론(H2 소제목 3~4개) → 핵심 요약 → 결론(CTA)
2. 서론: 독자의 관심을 끄는 질문/통계로 시작 (2~3문장)
3. 본론: 각 소제목(##) 아래 300~800자의 깊이 있는 분석
4. 핵심 요약: 3~5개 불릿 포인트로 핵심 정리
5. 결론: 독자에게 행동을 유도하는 CTA (질문, 생각 공유 요청 등)

[SEO 최적화 규칙]
- 제목에 핵심 키워드 자연스럽게 포함
- 첫 문단에 메인 키워드 1회 이상 포함
- H2 소제목에 롱테일 키워드 배치
- 본문 내 키워드 밀도 2~3% 유지 (과하지 않게)
- 자연스러운 문장 흐름 최우선

[톤앤매너]
- 전문적이면서도 읽기 편한 문체
- "~습니다" 어체 (블로그 합체)
- 적절한 비유와 예시로 이해도 향상
- 단정적 표현보다 분석적 시각 유지

[절대 금지]
- AI 느낌나는 기계적 문체 ("~에 대해 알아보겠습니다", "마무리하며")
- 과도한 이모지/특수문자 남용
- 근거 없는 주장이나 과장
- 다른 블로그 복사 느낌의 천편일률적 구성

[JSON만 출력]
{"posts":[{
  "type":"심층 분석",
  "title":"블로그 제목 (40자 이내)",
  "subtitle":"부제목 (30자 이내)",
  "content":"마크다운 형식 본문 (## 소제목 포함, 2000~5000자)",
  "seo_keywords":["키워드1","키워드2","키워드3","키워드4","키워드5"],
  "meta_description":"메타 설명 (150자 이내)",
  "thumbnail_suggestion":"썸네일 이미지 키워드 제안"
}]}"""


def _system_blog_post(tone: str, editorial_profile: str = "classic") -> str:
    if editorial_profile == "report":
        return _REPORT_BLOG_SYSTEM
    if tone == "joongyeon":
        return _BLOG_SYSTEM_JOONGYEON
    return (
        f"네이버 블로그 전문 작가. 말투: {tone}\n"
        "2,000~5,000자의 SEO 최적화된 블로그 포스트 작성.\n"
        "구조: 서론(후킹) → 본론(H2 3~4개) → 핵심 요약 → 결론(CTA)\n"
        "첫 문단에 핵심 키워드 포함. 자연스럽고 깊이 있는 분석.\n\n"
        '[JSON만 출력]\n'
        '{"posts":[{'
        '"type":"심층 분석",'
        '"title":"블로그 제목 (40자 이내)",'
        '"subtitle":"부제목 (30자 이내)",'
        '"content":"마크다운 형식 본문 (## 소제목 포함, 2000~5000자)",'
        '"seo_keywords":["키워드1","키워드2","키워드3"],'
        '"meta_description":"메타 설명 (150자 이내)",'
        '"thumbnail_suggestion":"썸네일 키워드"'
        '}]}'
    )


async def generate_blog_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
) -> list[GeneratedTweet]:
    """네이버 블로그용 SEO 최적화 장문 콘텐츠 비동기 생성.

    [v12.0] 2,000~5,000자의 구조화된 블로그 포스트.
    서론-본론(H2)-요약-결론 구성 + SEO 키워드 + 메타 설명.
    """
    from datetime import datetime as _dt
    report_profile = _use_report_profile(config)
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    deep_why_section = _build_deep_why_section(trend)
    fact_guardrail_section = _build_fact_guardrail_section(trend)
    identity_section = _build_account_identity_section(config, include_tone=not report_profile)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")
    min_words = getattr(config, "blog_min_words", 2000)
    max_words = getattr(config, "blog_max_words", 5000)
    seo_count = getattr(config, "blog_seo_keywords_count", 5)

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{identity_section}{fact_guardrail_section}{deep_why_section}{context_section}{scoring_section}\n"
        f"위 배경과 컨텍스트를 깊이 소화한 뒤, 네이버 블로그용 심층 분석 글을 작성.\n"
        f"글자 수: {min_words}~{max_words}자\n"
        f"SEO 키워드: {seo_count}개 제안\n"
        "핵심: 단순 뉴스 전달이 아니라 '이 현상에 대한 전문가 시각의 분석과 인사이트'.\n"
        "컨텍스트의 구체적 수치/사건/반응을 반드시 활용하고,\n"
        + (
            "## 왜 지금 중요한가 / ## 무슨 신호가 보이나 / ## 무엇을 봐야 하나 / ## 핵심 정리 구조를 지킬 것.\n"
            if report_profile
            else
            "소제목(##)으로 구분된 마크다운 구조를 지켜 작성할 것.\n"
        )
        + "반드시 JSON만 출력.\n"
    )

    try:
        response = await client.acreate(
            tier=TaskTier.HEAVY,
            max_tokens=6000,
            policy=_JSON_POLICY,
            system=_system_blog_post(config.tone, config.editorial_profile),
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json(response.text)

        if not data:
            log.warning(f"블로그 생성 JSON 파싱 실패: {trend.keyword}")
            return []

        posts = []
        for p in data.get("posts", []):
            content = p.get("content", "")
            title = p.get("title", "")
            subtitle = p.get("subtitle", "")
            seo_kws = p.get("seo_keywords", [])
            meta_desc = p.get("meta_description", "")
            thumb = p.get("thumbnail_suggestion", "")

            # 제목+부제 + 본문 결합
            full_content = f"# {title}\n"
            if subtitle:
                full_content += f"*{subtitle}*\n\n"
            full_content += content
            if meta_desc:
                full_content += f"\n\n---\n📋 메타 설명: {meta_desc}"
            if thumb:
                full_content += f"\n🖼️ 썸네일 제안: {thumb}"

            posts.append(GeneratedTweet(
                tweet_type=p.get("type", "블로그"),
                content=full_content,
                content_type="naver_blog",
                platform="naver_blog",
                seo_keywords=seo_kws[:seo_count],
            ))

        log.info(
            f"블로그 생성 완료: '{trend.keyword}' "
            f"({len(posts)}편, 총 {sum(p.char_count for p in posts)}자)"
        )
        return posts

    except Exception as e:
        log.error(f"블로그 생성 실패 ({trend.keyword}): {e}")
        return []


# ══════════════════════════════════════════════════════
#  4) X 쓰레드 (Premium+ 강화: 2트윗) — Sonnet tier
# ══════════════════════════════════════════════════════

async def generate_thread_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    tier: TaskTier = TaskTier.HEAVY,
) -> GeneratedThread | None:
    """고바이럴 트렌드용 강화 쓰레드 비동기 생성 (기본 Sonnet, 경량 카테고리는 Haiku)."""
    context_text = trend.context.to_combined_text() if trend.context else ""
    target_language = _resolve_language(config)
    safe_keyword = sanitize_keyword(trend.keyword)
    angles_text = ", ".join(trend.suggested_angles) if trend.suggested_angles else "없음"

    user_message = (
        f"주제: {safe_keyword}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n\n"
        f"[실시간 데이터]\n{context_text}\n\n"
        f"[분석 요약]\n"
        f"- 바이럴 점수: {trend.viral_potential}/100\n"
        f"- 핵심: {trend.top_insight}\n"
        f"- 추천 훅: {trend.best_hook_starter}\n"
        f"- 추천 앵글: {angles_text}\n\n"
        "위 데이터를 기반으로 정확히 2개 트윗의 바이럴 쓰레드를 JSON 형식으로 작성해주세요.\n"
        "첫 트윗(훅)은 최대 2,500자까지 충분히 길게 작성 가능합니다.\n"
        "나머지 트윗도 각 500~1,000자로 깊이 있게 작성해주세요."
    )

    try:
        response = await client.acreate(
            tier=tier,
            max_tokens=5000,
            policy=_JSON_POLICY,
            system=_system_thread(config.tone),
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json(response.text)

        if not data:
            log.warning(f"쓰레드 JSON 파싱 실패: {trend.keyword}")
            return None

        thread_tweets = data.get("tweets", [])
        hook = data.get("hook", thread_tweets[0] if thread_tweets else "")

        total_chars = sum(len(t) for t in thread_tweets)
        log.info(f"쓰레드 생성 완료: '{trend.keyword}' ({len(thread_tweets)}개 트윗, 총 {total_chars}자)")
        return GeneratedThread(tweets=thread_tweets, hook=hook)

    except Exception as e:
        log.error(f"쓰레드 생성 실패 ({trend.keyword}): {e}")
        return None


# ══════════════════════════════════════════════════════
#  5) 통합 배치 생성: 단문 5종 + Threads 2종 (1회 호출) — Haiku tier
# ══════════════════════════════════════════════════════

async def generate_tweets_and_threads_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None = None,
    golden_refs: list | None = None,
    pattern_weights: dict | None = None,
) -> TweetBatch | None:
    """단문 트윗과 Threads를 품질 우선으로 분리 생성한 뒤 배치로 합친다."""
    if _PY314_SERIAL_GENERATION:
        try:
            tweet_result = await generate_tweets_async(
                trend, config, client, recent_tweets, golden_refs, pattern_weights
            )
        except Exception as exc:
            tweet_result = exc

        try:
            threads_result = await generate_threads_content_async(trend, config, client)
        except Exception as exc:
            threads_result = exc
    else:
        tweet_result, threads_result = await asyncio.gather(
            generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights),
            generate_threads_content_async(trend, config, client),
            return_exceptions=True,
        )

    if isinstance(tweet_result, Exception):
        log.error(f"통합 생성(트윗) 실패 ({trend.keyword}): {tweet_result}")
        return None

    batch = tweet_result
    if not batch:
        return None

    if isinstance(threads_result, Exception):
        log.warning(f"통합 생성(Threads) 실패 ({trend.keyword}): {threads_result}")
    elif threads_result:
        batch.threads_posts = threads_result

    log.info(
        f"통합 생성 완료: '{trend.keyword}' "
        f"(트윗 {len(batch.tweets)}개 + Threads {len(batch.threads_posts)}개)"
    )
    return batch


# ══════════════════════════════════════════════════════
#  Async Orchestrator — 트렌드 내 모든 생성 병렬 실행
# ══════════════════════════════════════════════════════

async def generate_for_trend_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None = None,
    golden_refs: list | None = None,
    pattern_weights: dict | None = None,
) -> TweetBatch | None:
    """
    오케스트레이터 (비동기): 트윗 5종 + 조건부 장문/Threads/쓰레드/블로그 동시 생성.

    C1 최적화: Threads 활성 시 단문+Threads를 통합 1회 호출로 처리.
    [v12.0] target_platforms 기반 멀티플랫폼 라우팅.
    [v9.0] recent_tweets: 이전 생성 표현 주입 (콘텐츠 다양성).
    [v5.0] golden_refs / pattern_weights: 성과 기반 벤치마크 + 패턴 가중치.
    """
    # Phase 4: 카테고리 기반 티어 결정
    gen_tier = _select_generation_tier(trend, config)
    category = getattr(trend, "category", "") or "미분류"
    tier_label = "Sonnet" if gen_tier == TaskTier.HEAVY else "Haiku↓"
    platforms = getattr(config, "target_platforms", ["x"])

    # Threads 활성 여부 확인
    threads_enabled = (
        config.enable_threads
        and trend.viral_potential >= config.threads_min_score
        and "threads" in platforms
    )

    # [v12.0] 블로그 활성 여부
    blog_enabled = (
        "naver_blog" in platforms
        and trend.viral_potential >= getattr(config, "blog_min_score", 70)
    )

    # C3: 생성 티어 표시 (비용 투명성)
    tier_parts = ["단문(5종)" + ("+Threads(통합)" if threads_enabled else "")]
    if config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
        tier_parts.append(f"Premium+장문({tier_label})")
    if trend.viral_potential >= config.thread_min_score:
        tier_parts.append(f"X쓰레드({tier_label})")
    if blog_enabled:
        tier_parts.append("블로그(HEAVY)")
    log.info(f"  [{trend.viral_potential}점/{category}] '{trend.keyword}' → {' + '.join(tier_parts)}")

    if _PY314_SERIAL_GENERATION:
        result_map: dict[str, Any] = {}
        try:
            if threads_enabled:
                result_map["combined"] = await generate_tweets_and_threads_async(
                    trend, config, client, recent_tweets, golden_refs, pattern_weights
                )
            else:
                result_map["tweets"] = await generate_tweets_async(
                    trend, config, client, recent_tweets, golden_refs, pattern_weights
                )
        except Exception as exc:
            result_map["combined" if threads_enabled else "tweets"] = exc

        if config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
            try:
                result_map["long"] = await generate_long_form_async(trend, config, client, tier=gen_tier)
            except Exception as exc:
                result_map["long"] = exc

        if trend.viral_potential >= config.thread_min_score:
            try:
                result_map["thread"] = await generate_thread_async(trend, config, client, tier=gen_tier)
            except Exception as exc:
                result_map["thread"] = exc

        if blog_enabled:
            try:
                result_map["blog"] = await generate_blog_async(trend, config, client)
            except Exception as exc:
                result_map["blog"] = exc

        if "combined" in result_map:
            combined = result_map["combined"]
            if combined and not isinstance(combined, Exception):
                batch = combined
            else:
                if isinstance(combined, Exception):
                    log.warning(f"combined generation failed, falling back: {combined}")

                try:
                    fallback_tweets = await generate_tweets_async(
                        trend, config, client, None, golden_refs, pattern_weights
                    )
                except Exception as exc:
                    fallback_tweets = exc

                try:
                    fallback_threads = await generate_threads_content_async(trend, config, client)
                except Exception as exc:
                    fallback_threads = exc

                batch = fallback_tweets if not isinstance(fallback_tweets, Exception) else None
                if batch and not isinstance(fallback_threads, Exception) and fallback_threads:
                    batch.threads_posts = fallback_threads
        else:
            batch = result_map.get("tweets")

        if not batch or isinstance(batch, Exception):
            if isinstance(batch, Exception):
                log.error(f"tweet generation exception ({trend.keyword}): {batch}")
            return None

        long_result = result_map.get("long")
        if long_result and not isinstance(long_result, Exception):
            batch.long_posts = long_result

        thread_result = result_map.get("thread")
        if thread_result and not isinstance(thread_result, Exception):
            batch.thread = thread_result

        blog_result = result_map.get("blog")
        if blog_result and not isinstance(blog_result, Exception):
            batch.blog_posts = blog_result

        return batch

    tasks: dict[str, asyncio.Task] = {}

    # C1 최적화: Threads 가능하면 통합 호출, 아니면 기존 개별 호출
    if threads_enabled:
        tasks["combined"] = asyncio.ensure_future(
            generate_tweets_and_threads_async(trend, config, client, recent_tweets, golden_refs, pattern_weights)
        )
    else:
        tasks["tweets"] = asyncio.ensure_future(
            generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights)
        )

    if config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
        tasks["long"] = asyncio.ensure_future(generate_long_form_async(trend, config, client, tier=gen_tier))

    if trend.viral_potential >= config.thread_min_score:
        tasks["thread"] = asyncio.ensure_future(generate_thread_async(trend, config, client, tier=gen_tier))

    # [v12.0] 네이버 블로그 생성 (병렬)
    if blog_enabled:
        tasks["blog"] = asyncio.ensure_future(generate_blog_async(trend, config, client))

    keys = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    result_map = dict(zip(keys, results))

    # 통합 호출 결과 처리 (폴백 포함)
    if "combined" in result_map:
        combined = result_map["combined"]
        if combined and not isinstance(combined, Exception):
            batch = combined
        else:
            # 통합 실패 → 개별 폴백
            if isinstance(combined, Exception):
                log.warning(f"통합 생성 예외, 개별 폴백: {combined}")
            fallback_results = await asyncio.gather(
                generate_tweets_async(trend, config, client, None, golden_refs, pattern_weights),
                generate_threads_content_async(trend, config, client),
                return_exceptions=True,
            )
            batch = fallback_results[0] if not isinstance(fallback_results[0], Exception) else None
            if batch and not isinstance(fallback_results[1], Exception) and fallback_results[1]:
                batch.threads_posts = fallback_results[1]
    else:
        batch = result_map.get("tweets")

    if not batch or isinstance(batch, Exception):
        if isinstance(batch, Exception):
            log.error(f"트윗 생성 예외 ({trend.keyword}): {batch}")
        return None

    long_result = result_map.get("long")
    if long_result and not isinstance(long_result, Exception):
        batch.long_posts = long_result

    thread_result = result_map.get("thread")
    if thread_result and not isinstance(thread_result, Exception):
        batch.thread = thread_result

    # [v12.0] 블로그 결과 병합
    blog_result = result_map.get("blog")
    if blog_result and not isinstance(blog_result, Exception):
        batch.blog_posts = blog_result

    return batch


def generate_for_trend(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
) -> TweetBatch | None:
    """동기 래퍼 (하위 호환)."""
    return run_async(generate_for_trend_async(trend, config, client))


# ══════════════════════════════════════════════════════
#  Phase 4: A/B 변형 생성
# ══════════════════════════════════════════════════════

_AB_TONE_B = "직설적이고 논쟁적인 논평가"  # 변형 B 고정 톤


async def generate_ab_variant_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
) -> TweetBatch | None:
    """
    A/B 변형 B: 기본 톤과 다른 스타일(직설적·논쟁적)로 단문 트윗 5종 생성.
    결과 tweets의 variant_id="B", language=기본언어.
    실패 시 None 반환.
    """
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    safe_keyword = sanitize_keyword(trend.keyword)

    user_message = (
        f"오늘 다룰 주제/상황: {safe_keyword}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{context_section}{scoring_section}\n"
        "위 데이터를 참고하여 5가지 유형의 트윗 시안을 JSON 형식으로만 작성해주세요.\n"
        "반드시 JSON만 출력하고 다른 설명은 일절 없어야 합니다."
    )

    try:
        response = await client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=1500,
            policy=_JSON_POLICY,
            system=_system_tweets(_AB_TONE_B),
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json(response.text)
        if not data:
            return None

        tweets = []
        for t in data.get("tweets", []):
            content = t.get("content", "")
            if len(content) > 280:
                content = content[:277] + "..."
            tweets.append(GeneratedTweet(
                tweet_type=t.get("type", ""),
                content=content,
                content_type="short",
                variant_id="B",
                language=config.target_languages[0] if config.target_languages else "ko",
            ))

        log.info(f"A/B 변형 B 생성 완료: '{trend.keyword}' ({len(tweets)}개)")
        return TweetBatch(topic=data.get("topic", trend.keyword), tweets=tweets, viral_score=trend.viral_potential)

    except Exception as e:
        log.error(f"A/B 변형 B 생성 실패 ({trend.keyword}): {e}")
        return None


# -- backward-compat re-exports --
from content_qa import (  # noqa: F401
    audit_generated_content,
    regenerate_content_groups,
)
from multilang import (  # noqa: F401
    generate_for_trend_multilang_async,
)
from generation.persona import select_persona, _round_robin_counter  # noqa: F401,E501

