"""generation/marl.py — MARL 강화 트윗 생성 (v16.0).

generator.py에서 추출된 모듈.
"""

from loguru import logger as log
from shared.llm import LLMClient, TaskTier
from shared.llm.models import LLMPolicy

from config import AppConfig
from models import GeneratedTweet, ScoredTrend, TweetBatch
from prompt_builder import (
    _build_account_identity_section,
    _build_category_tone_hint,
    _build_context_section,
    _build_deep_why_section,
    _build_diversity_section,
    _build_golden_reference_section,
    _build_pattern_weights_section,
    _build_scoring_section,
    _parse_json,
    _resolve_language,
    _system_tweets,
)
from utils import sanitize_keyword

_JSON_POLICY = LLMPolicy(response_mode="json")


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
    # Lazy import to avoid circular dependency
    from shared.llm.marl import MARLConfig, MARLPipeline

    from generator import generate_tweets_async

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
            log.warning(f"[MARL] '{trend.keyword}' JSON 파싱 실패 → 기존 방식 폴백")
            return await generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights)

        tweets = []
        for t in data.get("tweets", []):
            content = t.get("content", "")
            if len(content) > 280:
                content = content[:277] + "..."
                log.warning(f"[MARL] 트윗 280자 초과 트리밍: {trend.keyword}")
            tweets.append(
                GeneratedTweet(
                    tweet_type=t.get("type", ""),
                    content=content,
                    content_type="short",
                    best_posting_time=t.get("best_posting_time", ""),
                    expected_engagement=t.get("expected_engagement", ""),
                    reasoning=t.get("reasoning", ""),
                )
            )

        log.info(f"[MARL] 트윗 생성 완료: '{trend.keyword}' " f"({len(tweets)}개, stages={result.stages_completed})")
        return TweetBatch(
            topic=data.get("topic", trend.keyword),
            tweets=tweets,
            viral_score=trend.viral_potential,
        )

    except Exception as e:
        log.warning(f"[MARL] 생성 실패 '{trend.keyword}': {e} → 기존 방식 폴백")
        return await generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights)
