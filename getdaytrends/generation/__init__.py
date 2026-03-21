"""generation/ — Content Generation Package for getdaytrends.

Phase 2.5 리펙토링: generator.py(2054줄)에서 점진적 추출 중.

구조:
- generator.py: 기존 모놀리식 파일 (핵심 로직)
- generation/persona.py: 퍼소나 선택 로직 (추출 완료)
- generation/prompts.py: 프롬프트 빌더 (마이그레이션 예정)
- generation/audit.py: QA 감사 로직 (마이그레이션 예정)
- generation/_common.py: 공통 유틸리티

공개 API:
    generate_for_trend_async(trend, config, client, recent_tweets=None) -> TweetBatch
    generate_for_trend(trend, config, client) -> TweetBatch  # sync wrapper
    generate_ab_variant_async(trend, config, client) -> TweetBatch
    generate_for_trend_multilang_async(trend, config, client) -> list[TweetBatch]
    audit_generated_content(batch, trend, config, client) -> dict
    select_persona(trend, config) -> str
"""


def __getattr__(name):
    """Lazy import to avoid circular dependency with generator.py."""
    # generator.py imports from generation.persona, so we can't eagerly
    # import from generator at module level (circular import).
    import generator as _gen
    _exports = {
        "generate_for_trend_async": _gen.generate_for_trend_async,
        "generate_for_trend": _gen.generate_for_trend,
        "generate_tweets_async": _gen.generate_tweets_async,
        "generate_tweets_and_threads_async": _gen.generate_tweets_and_threads_async,
        "generate_long_form_async": _gen.generate_long_form_async,
        "generate_threads_content_async": _gen.generate_threads_content_async,
        "generate_blog_async": _gen.generate_blog_async,
        "generate_thread_async": _gen.generate_thread_async,
        "generate_ab_variant_async": _gen.generate_ab_variant_async,
        "generate_for_trend_multilang_async": _gen.generate_for_trend_multilang_async,
        "audit_generated_content": _gen.audit_generated_content,
        "select_persona": _gen.select_persona,
    }
    if name in _exports:
        return _exports[name]
    raise AttributeError(f"module 'generation' has no attribute {name!r}")


__all__ = [
    "generate_for_trend_async",
    "generate_for_trend",
    "generate_tweets_async",
    "generate_tweets_and_threads_async",
    "generate_long_form_async",
    "generate_threads_content_async",
    "generate_blog_async",
    "generate_thread_async",
    "generate_ab_variant_async",
    "generate_for_trend_multilang_async",
    "audit_generated_content",
    "select_persona",
]
