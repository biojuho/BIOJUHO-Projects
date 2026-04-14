"""generation/long_form.py — 장문 콘텐츠 생성 (X Premium+, 네이버 블로그).

generator.py에서 추출된 모듈.
"""

from loguru import logger as log

from shared.llm import LLMClient, TaskTier
from shared.llm.models import LLMPolicy

try:
    from ..config import AppConfig
    from ..models import GeneratedTweet, ScoredTrend
    from ..prompt_builder import (
        _REPORT_BLOG_SYSTEM,
        _build_account_identity_section,
        _build_context_section,
        _build_deep_why_section,
        _build_fact_guardrail_section,
        _build_revision_feedback_section,
        _build_scoring_section,
        _parse_json,
        _resolve_language,
        _system_long_form,
        _use_report_profile,
    )
    from ..utils import sanitize_keyword
except ImportError:
    from config import AppConfig
    from models import GeneratedTweet, ScoredTrend
    from prompt_builder import (
        _REPORT_BLOG_SYSTEM,
        _build_account_identity_section,
        _build_context_section,
        _build_deep_why_section,
        _build_fact_guardrail_section,
        _build_revision_feedback_section,
        _build_scoring_section,
        _parse_json,
        _resolve_language,
        _system_long_form,
        _use_report_profile,
    )
    from utils import sanitize_keyword

_JSON_POLICY = LLMPolicy(response_mode="json")


# ══════════════════════════════════════════════════════
#  X Premium+ 장문 포스트 (1,500~3,000자) — Sonnet tier
# ══════════════════════════════════════════════════════


async def generate_long_form_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    tier: TaskTier = TaskTier.LIGHTWEIGHT,  # [v13.0] HEAVY→LIGHTWEIGHT 비용 절감
    *,
    revision_feedback: dict | None = None,
) -> list[GeneratedTweet]:
    """X Premium+ 장문 콘텐츠 2종 비동기 생성 (v13.0: LIGHTWEIGHT 기본)."""
    from datetime import datetime as _dt

    report_profile = _use_report_profile(config)
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    deep_why_section = _build_deep_why_section(trend)
    fact_guardrail_section = _build_fact_guardrail_section(trend)
    revision_feedback_section = _build_revision_feedback_section(revision_feedback)
    identity_section = _build_account_identity_section(config, include_tone=not report_profile)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{identity_section}{fact_guardrail_section}{deep_why_section}{context_section}{scoring_section}"
        f"{revision_feedback_section}\n"
        "위 '왜 지금 트렌드인가' 배경과 데이터/수치/반응을 깊이 소화한 뒤,\n"
        "읽는 사람이 '이건 저장해야 돼' 하는 장문 2종을 작성.\n"
        "핵심: 뉴스 요약 아님. 이 현상의 이면을 파고드는 분석과 해석.\n"
        "컨텍스트의 구체적 수치/사건/시점 정보를 반드시 활용할 것.\n"
        + (
            "1) 딥다이브 분석 (1,500~3,000자): 남들이 놓친 포인트 기반 분석\n"
            "2) 리포트 코멘트 (1,000~2,000자): 과장 없이 의미와 관찰 포인트 정리\n\n"
            if report_profile
            else "1) 딥다이브 분석 (1,500~3,000자): 남들이 놓친 포인트 기반 분석\n"
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
#  네이버 블로그 글감 (2,000~5,000자) — SEO 최적화
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
        "[JSON만 출력]\n"
        '{"posts":[{'
        '"type":"심층 분석",'
        '"title":"블로그 제목 (40자 이내)",'
        '"subtitle":"부제목 (30자 이내)",'
        '"content":"마크다운 형식 본문 (## 소제목 포함, 2000~5000자)",'
        '"seo_keywords":["키워드1","키워드2","키워드3"],'
        '"meta_description":"메타 설명 (150자 이내)",'
        '"thumbnail_suggestion":"썸네일 키워드"'
        "}]}"
    )


async def generate_blog_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    *,
    revision_feedback: dict | None = None,
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
    revision_feedback_section = _build_revision_feedback_section(revision_feedback)
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
        f"{identity_section}{fact_guardrail_section}{deep_why_section}{context_section}{scoring_section}"
        f"{revision_feedback_section}\n"
        f"위 배경과 컨텍스트를 깊이 소화한 뒤, 네이버 블로그용 심층 분석 글을 작성.\n"
        f"글자 수: {min_words}~{max_words}자\n"
        f"SEO 키워드: {seo_count}개 제안\n"
        "핵심: 단순 뉴스 전달이 아니라 '이 현상에 대한 전문가 시각의 분석과 인사이트'.\n"
        "컨텍스트의 구체적 수치/사건/반응을 반드시 활용하고,\n"
        + (
            "## 왜 지금 중요한가 / ## 무슨 신호가 보이나 / ## 무엇을 봐야 하나 / ## 핵심 정리 구조를 지킬 것.\n"
            if report_profile
            else "소제목(##)으로 구분된 마크다운 구조를 지켜 작성할 것.\n"
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

            posts.append(
                GeneratedTweet(
                    tweet_type=p.get("type", "블로그"),
                    content=full_content,
                    content_type="naver_blog",
                    platform="naver_blog",
                    seo_keywords=seo_kws[:seo_count],
                )
            )

        log.info(f"블로그 생성 완료: '{trend.keyword}' " f"({len(posts)}편, 총 {sum(p.char_count for p in posts)}자)")
        return posts

    except Exception as e:
        log.error(f"블로그 생성 실패 ({trend.keyword}): {e}")
        return []
