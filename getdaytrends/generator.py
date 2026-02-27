"""
getdaytrends v2.0 - Tweet & Thread Generation
컨텍스트 기반 트윗 5종 + 고바이럴 트렌드용 쓰레드 생성.
"""

import json
import logging
import re

import anthropic

from config import AppConfig
from models import GeneratedThread, GeneratedTweet, ScoredTrend, TweetBatch

log = logging.getLogger(__name__)

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


SYSTEM_PROMPT_THREAD = """당신은 X(트위터)에서 바이럴 쓰레드를 작성하는 전문가입니다.

하나의 트렌드 주제를 깊이 있게 다루는 3~5개 트윗으로 구성된 쓰레드를 작성합니다.

[쓰레드 구조]
1. 훅 트윗: 클릭을 유발하는 강렬한 도입부 (이모지 + 숫자 + 호기심)
2. 본문 트윗: 뉴스/데이터 기반 핵심 인사이트
3. 분석 트윗: 독자적 시각의 의견/분석
4. 마무리 트윗: CTA (리트윗/의견 요청) + 핵심 요약

[규칙]
- 각 트윗 280자 이내
- 첫 트윗이 가장 중요 (타임라인에서 보이는 부분)
- 번호 매기지 않음 (쓰레드 자체가 순서)

[출력 형식 - JSON만]
{
  "hook": "첫 번째 트윗 (훅)",
  "tweets": ["첫 번째 트윗", "두 번째 트윗", "세 번째 트윗", "마무리 트윗"]
}"""


def _parse_json_response(raw: str) -> dict | None:
    """Claude 응답에서 JSON 추출."""
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


def generate_tweets(
    trend: ScoredTrend,
    config: AppConfig,
    client: anthropic.Anthropic,
) -> TweetBatch | None:
    """
    바이럴 분석 결과 + 멀티소스 컨텍스트를 활용한 5종 트윗 생성.
    """
    # 컨텍스트 기반 프롬프트 구성
    context_section = ""
    if trend.context:
        combined = trend.context.to_combined_text()
        if combined:
            context_section = f"\n[수집된 실시간 컨텍스트]\n{combined}\n"

    scoring_section = ""
    if trend.viral_potential > 0:
        angles = ", ".join(trend.suggested_angles) if trend.suggested_angles else "없음"
        scoring_section = f"""
[바이럴 분석 결과]
- 바이럴 점수: {trend.viral_potential}/100
- 가속도: {trend.trend_acceleration}
- 핵심 인사이트: {trend.top_insight}
- 추천 앵글: {angles}
- 추천 훅: {trend.best_hook_starter}
"""

    language_map = {
        "korea": "한국어(Korean)",
        "us": "영어(English)",
        "japan": "일본어(Japanese)",
        "global": "영어(English)",
    }
    target_language = language_map.get((config.country or "").lower(), "한국어(Korean)")

    user_message = f"""오늘 다룰 주제/상황: {trend.keyword}
화자의 톤앤매너: {config.tone}
작성 언어: 반드시 {target_language}로 작성할 것
{context_section}{scoring_section}
위 데이터를 참고하여 5가지 유형의 트윗 시안을 JSON 형식으로만 작성해주세요.
반드시 JSON만 출력하고 다른 설명은 일절 없어야 합니다."""

    try:
        response = client.messages.create(
            model=config.claude_model,
            max_tokens=1500,
            system=SYSTEM_PROMPT_TWEETS,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text
        data = _parse_json_response(raw)

        if not data:
            log.error(f"트윗 생성 JSON 파싱 실패: {trend.keyword}")
            return None

        tweets = [
            GeneratedTweet(
                tweet_type=t.get("type", ""),
                content=t.get("content", ""),
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


def generate_thread(
    trend: ScoredTrend,
    config: AppConfig,
    client: anthropic.Anthropic,
) -> GeneratedThread | None:
    """
    고바이럴 트렌드용 멀티트윗 쓰레드 생성.
    viral_potential >= 80일 때만 호출.
    """
    context_text = trend.context.to_combined_text() if trend.context else ""

    language_map = {
        "korea": "한국어(Korean)",
        "us": "영어(English)",
        "japan": "일본어(Japanese)",
        "global": "영어(English)",
    }
    target_language = language_map.get((config.country or "").lower(), "한국어(Korean)")

    user_message = f"""주제: {trend.keyword}
톤앤매너: {config.tone}
작성 언어: 반드시 {target_language}로 작성할 것

[실시간 데이터]
{context_text}

[분석 요약]
- 바이럴 점수: {trend.viral_potential}/100
- 핵심: {trend.top_insight}
- 추천 훅: {trend.best_hook_starter}

위 데이터를 기반으로 바이럴 쓰레드를 JSON 형식으로 작성해주세요."""

    try:
        response = client.messages.create(
            model=config.claude_model,
            max_tokens=2000,
            system=SYSTEM_PROMPT_THREAD,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text
        data = _parse_json_response(raw)

        if not data:
            log.warning(f"쓰레드 JSON 파싱 실패: {trend.keyword}")
            return None

        thread_tweets = data.get("tweets", [])
        hook = data.get("hook", thread_tweets[0] if thread_tweets else "")

        log.info(f"쓰레드 생성 완료: '{trend.keyword}' ({len(thread_tweets)}개 트윗)")
        return GeneratedThread(tweets=thread_tweets, hook=hook)

    except Exception as e:
        log.error(f"쓰레드 생성 실패 ({trend.keyword}): {e}")
        return None


def generate_for_trend(
    trend: ScoredTrend,
    config: AppConfig,
    client: anthropic.Anthropic,
) -> TweetBatch | None:
    """
    오케스트레이터: 트윗 5종 생성 + 고점수 시 쓰레드 추가.
    """
    batch = generate_tweets(trend, config, client)
    if not batch:
        return None

    # 바이럴 점수 80 이상이면 쓰레드도 생성
    if trend.viral_potential >= 80:
        log.info(f"  고바이럴 트렌드 감지 (점수: {trend.viral_potential}) → 쓰레드 생성")
        thread = generate_thread(trend, config, client)
        if thread:
            batch.thread = thread

    return batch
