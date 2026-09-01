"""generation/ — Content Generation Package for getdaytrends.

v9.0 리팩토링 완료: generator.py(984→519줄)에서 서브모듈 추출 완료.

구조:
- generator.py: 핵심 오케스트레이션 (519줄)
- generation/persona.py: 퍼소나 선택 로직
- generation/long_form.py: 장문/블로그 생성 함수
- generation/threads.py: Meta Threads 콘텐츠 생성
- generation/marl.py: MARL 기반 멀티앵글 생성
- generation/system_prompts.py: 시스템 프롬프트 관리 (25KB)
- generation/prompts.py: 프롬프트 유틸리티
- generation/audit.py: 생성물 감사 로직
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
