"""generation/ — Content Generation Package for getdaytrends.

Phase 2 리펙토링: generator.py(1363줄)에서 추출된 모듈식 콘텐츠 생성 패키지.

현재 구조 (점진적 마이그레이션):
- generator.py: 기존 모놀리식 파일 (모든 로직 포함, 하위 호환 유지)
- generation/: 새 패키지 (generator.py의 공개 API를 re-export)

향후 마이그레이션:
1. generator.py의 각 섹션을 generation/ 하위 모듈로 이동
2. generator.py를 얇은 re-export 래퍼로 변환
3. 외부 코드는 `from generation import ...` 로 전환

공개 API:
    generate_for_trend_async(trend, config, client, recent_tweets=None) -> TweetBatch
    generate_for_trend(trend, config, client) -> TweetBatch  # sync wrapper
    generate_ab_variant_async(trend, config, client) -> TweetBatch
    generate_for_trend_multilang_async(trend, config, client) -> list[TweetBatch]
    audit_generated_content(batch, trend, config, client) -> dict
"""

# Phase 2: generator.py에서 공개 API를 re-export
# - 외부 코드가 `from generation import generate_for_trend_async` 로 사용 가능
# - generator.py의 코드를 건드리지 않고 점진적 마이그레이션 기반 마련
from generator import (  # noqa: F401
    generate_for_trend_async,
    generate_for_trend,
    generate_tweets_async,
    generate_tweets_and_threads_async,
    generate_long_form_async,
    generate_threads_content_async,
    generate_blog_async,
    generate_thread_async,
    generate_ab_variant_async,
    generate_for_trend_multilang_async,
    audit_generated_content,
)

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
]
