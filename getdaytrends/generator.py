"""
getdaytrends v2.1 - Tweet & Thread & Long-form & Threads Generation
컨텍스트 기반 트윗 3종 + X Premium+ 장문 + Meta Threads 3종 + 강화 쓰레드 3개.
"""

import json
import logging
import re
import sys
from pathlib import Path

# shared.llm 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import AppConfig
from models import GeneratedThread, GeneratedTweet, ScoredTrend, TweetBatch
from shared.llm import LLMClient, TaskTier

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
#  Language Helper
# ══════════════════════════════════════════════════════

_LANGUAGE_MAP = {
    "korea": "한국어(Korean)",
    "us": "영어(English)",
    "japan": "일본어(Japanese)",
    "global": "영어(English)",
}


def _resolve_language(config: AppConfig) -> str:
    return _LANGUAGE_MAP.get((config.country or "").lower(), "한국어(Korean)")


def _build_context_section(trend: ScoredTrend) -> str:
    if not trend.context:
        return ""
    combined = trend.context.to_combined_text()
    return f"\n[수집된 실시간 컨텍스트]\n{combined}\n" if combined else ""


def _build_scoring_section(trend: ScoredTrend) -> str:
    if trend.viral_potential <= 0:
        return ""
    angles = ", ".join(trend.suggested_angles) if trend.suggested_angles else "없음"
    return f"""
[바이럴 분석 결과]
- 바이럴 점수: {trend.viral_potential}/100
- 가속도: {trend.trend_acceleration}
- 핵심 인사이트: {trend.top_insight}
- 추천 앵글: {angles}
- 추천 훅: {trend.best_hook_starter}
"""


# ══════════════════════════════════════════════════════
#  JSON Parser
# ══════════════════════════════════════════════════════

def _parse_json_response(raw: str | None) -> dict | None:
    """Claude 응답에서 JSON 추출."""
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


# ══════════════════════════════════════════════════════
#  1) 기존 단문 트윗 5종 (280자)
# ══════════════════════════════════════════════════════

SYSTEM_PROMPT_TWEETS = """당신은 X(트위터) 트렌드에 민감하며, 팔로워들과의 티키타카(소통)에 능한
'소셜 커뮤니티 매니저 겸 카피라이터'입니다.

팔로워들이 무의식적으로 답글을 달고 싶게 만드는, 280자 이내의 임팩트 있는 트윗을 작성합니다.

[작성 가이드라인]
1. 공감과 논쟁: 누구나 공감할 수 있는 일상적 이야기나 가벼운 찬반 주제
2. 트렌드 결합: 밈(Meme)이나 X 특유의 텍스트 포맷 활용
3. 질문형 구조: 문장 끝을 질문으로 맺어 독자가 자신의 이야기를 꺼내도록 유도
4. 실시간 데이터 활용: 제공된 뉴스/Reddit/X 데이터를 자연스럽게 녹여서 구체성 확보
5. 각 트윗은 반드시 280자 이내

[출력 형식 - 반드시 JSON으로만 응답]
{
  "topic": "주제명",
  "tweets": [
    {"type": "공감 유도형", "content": "트윗 내용"},
    {"type": "가벼운 꿀팁형", "content": "트윗 내용"},
    {"type": "찬반 질문형", "content": "트윗 내용"},
    {"type": "동기부여/명언형", "content": "트윗 내용"},
    {"type": "유머/밈 활용형", "content": "트윗 내용"}
  ]
}"""


def generate_tweets(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
) -> TweetBatch | None:
    """바이럴 분석 결과 + 멀티소스 컨텍스트를 활용한 5종 트윗 생성."""
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)

    user_message = f"""오늘 다룰 주제/상황: {trend.keyword}
화자의 톤앤매너: {config.tone}
작성 언어: 반드시 {target_language}로 작성할 것
{context_section}{scoring_section}
위 데이터를 참고하여 5가지 유형의 트윗 시안을 JSON 형식으로만 작성해주세요.
반드시 JSON만 출력하고 다른 설명은 일절 없어야 합니다."""

    try:
        response = client.create(
            tier=TaskTier.HEAVY,
            max_tokens=1500,
            system=SYSTEM_PROMPT_TWEETS,
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json_response(response.text)

        if not data:
            log.error(f"트윗 생성 JSON 파싱 실패: {trend.keyword}")
            return None

        tweets = [
            GeneratedTweet(
                tweet_type=t.get("type", ""),
                content=t.get("content", ""),
                content_type="short",
            )
            for t in data.get("tweets", [])
        ]

        log.info(f"트윗 생성 완료: '{trend.keyword}' ({len(tweets)}개)")
        return TweetBatch(
            topic=data.get("topic", trend.keyword),
            tweets=tweets,
            viral_score=trend.viral_potential,
        )

    except Exception as e:
        log.error(f"Claude API 호출 실패 ({trend.keyword}): {e}")
        return None


# ══════════════════════════════════════════════════════
#  2) X Premium+ 장문 포스트 (1,500~3,000자)
# ══════════════════════════════════════════════════════

SYSTEM_PROMPT_LONG_FORM = """당신은 X(트위터) Premium+ 사용자를 위한 장문 콘텐츠 전문 작가입니다.
X Premium+는 최대 25,000자 포스트가 가능합니다.

당신은 트렌드 주제를 깊이 있게 분석하여 팔로워들이 저장하고 공유하고 싶은 고품질 장문 포스트를 작성합니다.

[작성 가이드라인]
1. 구조화된 분석: 소제목(이모지+텍스트), 번호 목록, 핵심 문장 강조 활용
2. 데이터 인용: 제공된 뉴스/Reddit/X 데이터를 구체적으로 인용하여 신뢰도 확보
3. 독창적 시각: 단순 정리가 아닌, 반직관적 해석과 미래 전망 포함
4. 읽기 쉬운 포맷: 줄바꿈, 공백, 이모지를 활용한 스캔 가능한 구조
5. 강한 도입부: 첫 2줄이 타임라인에서 보이므로 강렬한 훅 필수
6. CTA 마무리: 의견 요청, 리포스트 유도로 마무리

[출력 형식 - JSON만]
{
  "posts": [
    {"type": "딥다이브 분석", "content": "1,500~2,500자 분석 글"},
    {"type": "핫테이크 오피니언", "content": "1,000~2,000자 의견 글"}
  ]
}"""


def generate_long_form(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
) -> list[GeneratedTweet]:
    """X Premium+ 장문 콘텐츠 2종 생성 (딥다이브 + 핫테이크)."""
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)

    user_message = f"""주제: {trend.keyword}
톤앤매너: {config.tone}
작성 언어: 반드시 {target_language}로 작성할 것
{context_section}{scoring_section}
위 데이터를 기반으로 X Premium+ 장문 포스트 2종을 JSON으로 작성해주세요.
1) 딥다이브 분석 (1,500~2,500자): 데이터 기반 구조화된 분석
2) 핫테이크 오피니언 (1,000~2,000자): 논쟁적이고 감정을 자극하는 의견

반드시 JSON만 출력하세요."""

    try:
        response = client.create(
            tier=TaskTier.HEAVY,
            max_tokens=6000,
            system=SYSTEM_PROMPT_LONG_FORM,
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json_response(response.text)

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
#  3) Meta Threads 콘텐츠 (500자)
# ══════════════════════════════════════════════════════

SYSTEM_PROMPT_THREADS = """당신은 Meta Threads 플랫폼 전문 콘텐츠 크리에이터입니다.
Threads는 500자 제한이며, X보다 캐주얼하고 대화적인 톤이 특징입니다.

[Threads 특성]
- 이모지와 줄바꿈을 적극 활용
- 마치 친구에게 말하듯 캐주얼한 톤
- 시각적 텍스트 구조 (줄바꿈으로 호흡 조절)
- 인스타그램 사용자층과 겹침 → 비주얼 감성 중시

[출력 형식 - JSON만]
{
  "posts": [
    {"type": "훅 포스트", "content": "스크롤 멈추게 하는 도입 (500자 이내)"},
    {"type": "참여형 포스트", "content": "질문+공감 유도 (500자 이내)"}
  ]
}"""


def generate_threads_content(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
) -> list[GeneratedTweet]:
    """Meta Threads 최적화 콘텐츠 5종 생성."""
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)

    user_message = f"""주제: {trend.keyword}
톤앤매너: {config.tone} (단, Threads에 맞게 더 캐주얼하고 친근하게)
작성 언어: 반드시 {target_language}로 작성할 것
{context_section}{scoring_section}
위 데이터를 기반으로 Meta Threads 콘텐츠를 JSON으로 작성해주세요.
1) 훅 포스트: 타임라인에서 스크롤을 멈추게 하는 강렬한 도입
2) 참여형 포스트: 공감 + 질문으로 댓글 유도

각 포스트 500자 이내. 반드시 JSON만 출력하세요."""

    try:
        response = client.create(
            tier=TaskTier.HEAVY,
            max_tokens=4000,
            system=SYSTEM_PROMPT_THREADS,
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json_response(response.text)

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
#  4) X 쓰레드 (Premium+ 강화: 5-8트윗, 장문 혼합)
# ══════════════════════════════════════════════════════

SYSTEM_PROMPT_THREAD = """당신은 X(트위터)에서 바이럴 쓰레드를 작성하는 전문가입니다.
작성자는 X Premium+ 사용자로, 각 트윗에 최대 25,000자까지 작성할 수 있습니다.

하나의 트렌드 주제를 깊이 있게 다루는 정확히 2개 트윗으로 구성된 쓰레드를 작성합니다.

[쓰레드 구조 - 반드시 2개]
1. 🪝 훅 트윗 (최대 2,500자): 타임라인에서 "더보기"를 누르게 만드는 강렬한 도입부. 핵심 주장 + 데이터 + 호기심 유발. 충분히 길게 작성해도 됩니다.
2. 🎯 마무리 트윗 (500~1,000자): 핵심 인사이트 + CTA + 리트윗/의견 요청

[규칙]
- 첫 트윗(훅)이 가장 중요하며, 길게 작성 가능 (최대 2,500자)
- 이모지 섹션 헤더로 각 트윗의 역할 구분
- 번호 매기지 않음 (쓰레드 자체가 순서)
- 실시간 데이터를 적극 인용
- 반드시 정확히 2개 트윗

[출력 형식 - JSON만]
{
  "hook": "첫 번째 트윗 (훅, 최대 2,500자)",
  "tweets": ["첫 번째 트윗 (훅)", "두 번째 트윗 (마무리 CTA)"]
}"""


def generate_thread(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
) -> GeneratedThread | None:
    """고바이럴 트렌드용 강화 쓰레드 생성 (Premium+ 장문 혼합, 5-8트윗)."""
    context_text = trend.context.to_combined_text() if trend.context else ""
    target_language = _resolve_language(config)

    user_message = f"""주제: {trend.keyword}
톤앤매너: {config.tone}
작성 언어: 반드시 {target_language}로 작성할 것

[실시간 데이터]
{context_text}

[분석 요약]
- 바이럴 점수: {trend.viral_potential}/100
- 핵심: {trend.top_insight}
- 추천 훅: {trend.best_hook_starter}
- 추천 앵글: {', '.join(trend.suggested_angles) if trend.suggested_angles else '없음'}

위 데이터를 기반으로 정확히 2개 트윗의 바이럴 쓰레드를 JSON 형식으로 작성해주세요.
첫 트윗(훅)은 최대 2,500자까지 충분히 길게 작성 가능합니다.
나머지 트윗도 각 500~1,000자로 깊이 있게 작성해주세요."""

    try:
        response = client.create(
            tier=TaskTier.HEAVY,
            max_tokens=8000,
            system=SYSTEM_PROMPT_THREAD,
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json_response(response.text)

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
#  Orchestrator
# ══════════════════════════════════════════════════════

def generate_for_trend(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
) -> TweetBatch | None:
    """
    오케스트레이터: 트윗 5종 + 조건부 장문/Threads/쓰레드 생성.
    """
    batch = generate_tweets(trend, config, client)
    if not batch:
        return None

    # X Premium+ 장문 (바이럴 점수 기준)
    if config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
        log.info(f"  장문 생성 (점수: {trend.viral_potential} ≥ {config.long_form_min_score})")
        batch.long_posts = generate_long_form(trend, config, client)

    # Meta Threads 콘텐츠
    if config.enable_threads:
        log.info(f"  Threads 콘텐츠 생성")
        batch.threads_posts = generate_threads_content(trend, config, client)

    # 바이럴 점수 80 이상이면 강화 쓰레드도 생성
    if trend.viral_potential >= 80:
        log.info(f"  고바이럴 트렌드 감지 (점수: {trend.viral_potential}) → 강화 쓰레드 생성")
        thread = generate_thread(trend, config, client)
        if thread:
            batch.thread = thread

    return batch
