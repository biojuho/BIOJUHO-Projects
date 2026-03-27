"""
getdaytrends — Multilang Generation
다국어 생성 지원.
generator.py에서 분리됨.
"""

import asyncio
import json
import re

from config import AppConfig
from models import GeneratedThread, GeneratedTweet, ScoredTrend, TweetBatch
from shared.llm import LLMClient, TaskTier
from shared.llm.models import LLMPolicy
from utils import sanitize_keyword

from loguru import logger as log

_JSON_POLICY = LLMPolicy(response_mode="json")



# ══════════════════════════════════════════════════════
#  Phase 4: 멀티언어 생성
# ══════════════════════════════════════════════════════

async def generate_for_trend_multilang_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
) -> list[TweetBatch]:
    """
    멀티언어 생성 오케스트레이터 (Phase 4).
    config.target_languages 목록의 각 언어마다 단문 트윗 5종을 생성.
    생성된 TweetBatch.tweets[*].language = 해당 언어 코드.
    기본 언어(target_languages[0])는 primary 배치로 반환됨.

    enable_multilang=False 또는 언어 1개이면 빈 리스트 반환 (호출 측에서 처리).
    """
    if not getattr(config, "enable_multilang", False) or len(config.target_languages) <= 1:
        return []

    async def _gen_for_lang(lang_code: str) -> TweetBatch | None:
        lang_name = _LANG_NAME_MAP.get(lang_code, lang_code)
        safe_keyword = sanitize_keyword(trend.keyword)
        context_section = _build_context_section(trend)
        scoring_section = _build_scoring_section(trend)

        user_message = (
            f"오늘 다룰 주제/상황: {safe_keyword}\n"
            f"작성 언어: 반드시 {lang_name}로 작성할 것\n"
            f"{context_section}{scoring_section}\n"
            "위 데이터를 참고하여 5가지 유형의 트윗 시안을 JSON 형식으로만 작성해주세요.\n"
            "반드시 JSON만 출력하고 다른 설명은 일절 없어야 합니다."
        )
        try:
            response = await client.acreate(
                tier=TaskTier.LIGHTWEIGHT,
                max_tokens=1500,
                policy=_JSON_POLICY,
                system=_system_tweets(config.tone),
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
                    language=lang_code,
                ))

            log.info(f"멀티언어 [{lang_code}] 생성 완료: '{trend.keyword}' ({len(tweets)}개)")
            return TweetBatch(
                topic=data.get("topic", trend.keyword),
                tweets=tweets,
                viral_score=trend.viral_potential,
                language=lang_code,
            )
        except Exception as e:
            log.error(f"멀티언어 [{lang_code}] 생성 실패 ({trend.keyword}): {e}")
            return None

    # 기본 언어 제외한 추가 언어만 생성 (기본 언어는 메인 파이프라인에서 처리)
    extra_langs = config.target_languages[1:]
    results = await asyncio.gather(*[_gen_for_lang(lang) for lang in extra_langs], return_exceptions=True)

    batches: list[TweetBatch] = []
    for lang, result in zip(extra_langs, results):
        if isinstance(result, Exception):
            log.error(f"멀티언어 [{lang}] 예외 ({trend.keyword}): {result}")
        elif result is not None:
            batches.append(result)

    return batches


# ══════════════════════════════════════════════════════
#  v12.0: Content Quality Audit — 7축 채점 시스템
#  (v11 5축 + regulation/algorithm 2축 추가)
# ══════════════════════════════════════════════════════

_CONTENT_QA_SYSTEM = """콘텐츠 품질 심사관. 7개 축으로 채점 (총 100점).
핵심 평가 기준: "이 글이 사람이 쓴 것 같은가, AI가 쓴 것 같은가?"

[채점 축]
1. hook (훅 임팩트, 0~20): 첫 문장이 타임라인에서 스크롤을 멈추게 하는가
   - 20점: 구체적 숫자/반전/체감 환산으로 즉각 주목 ("3일 만에 2000억 증발", "월급 250만원 받는 사람한테 이게 의미하는 거")
   - 10점: 관심은 가지만 뻔한 시작 ("최근 XX가 주목받고 있는데")
   - 0점: "오늘 XX 이슈가..." 식 뉴스 요약 / 키워드를 첫 문장에 그대로 반복 ("XX가 화제다")

2. fact (팩트 일관성, 0~15): 제공된 컨텍스트의 데이터/사실과 일치하는가
   - 15점: 컨텍스트 수치/팩트를 정확히 활용하고 일상 스케일로 환산
   - 8점: 대체로 맞지만 구체성 부족 (숫자 없이 "많이 올랐다" 수준)
   - 0점: 사실과 다르거나 근거 없는 주장, "전문가들은 ~라고 말했다" 식 출처 불명 인용

3. tone (톤 일관성, 0~15): 뉴스를 보고 '한마디 하는 사람' 톤을 유지하는가
   - 15점: "~인 거임" "솔직히" "근데 진짜" 등 자연스러운 MZ 구어체. 정보 30% + 해석 70%
   - 8점: 구어체이나 중간중간 기자체/설명체 혼재 ("~에 대해 살펴보면")
   - 0점: AI 어투 감지 즉시 0점. 아래 패턴 중 하나라도 있으면 0점:
     * "화제가 되고 있다" "주목받고 있다" "관심이 쏠리고 있다" (기자체)
     * "~인 것 같습니다" "~해야 합니다" "~라고 할 수 있습니다" (AI 경어체)
     * "~에 대해 알아보겠습니다" "~를 분석해보면" (설명체)
     * "여러분" "우리 모두" (연설체)
     * "앞으로의 변화가 기대된다" "귀추가 주목된다" (상투구)
     * "전문가에 따르면" "~라는 분석이다" (간접 인용)

4. kick (킥 품질, 0~15): 마무리가 캡처/공유 욕구를 자극하는가
   - 15점: 뼈때리는 펀치라인. 패턴 예시: "근데 진짜 무서운 건 이게 시작이라는 거임" / "우리가 할 수 있는 건 출근하는 것뿐"
   - 8점: 마무리는 있으나 뻔함 ("지켜봐야 할 것 같다" 수준)
   - 0점: 그냥 끝나거나 "~했으면 좋겠다" / "앞으로의 변화가 기대된다" 식 상투구

5. angle (유니크 앵글, 0~15): 뻔한 뉴스 요약이 아닌 독자적 시각이 있는가
   - 15점: "이런 각도는 처음이다" 싶은 해석. 남들이 놓치는 포인트를 짚음
   - 8점: 약간의 시각 차별화 시도하나 누구나 할 수 있는 수준
   - 0점: 뉴스 기사를 문체만 바꿔 옮긴 것 (정보 전달 >50%, 해석 <50%)

6. regulation (규제 준수, 0~10): 플랫폼별 규제 가이드라인을 준수하는가
   - 10점: 해시태그 0개, 외부 링크 0개, 이모지 2개 이하
   - 5점: 대부분 준수하나 일부 위반 가능성 (외부 링크 포함, 해시태그 1~2개)
   - 0점: 명백한 규제 위반 (해시태그 남용, Shadowban 트리거 패턴)

7. algorithm (알고리즘 최적화, 0~10): 해당 플랫폼 알고리즘이 우대하는 형태인가
   - 10점: 알고리즘 우대 요소 적극 반영 (체류 시간 확보, 인용 RT 유도, 댓글 유도 등)
   - 5점: 기본적 최적화만 충족
   - 0점: 알고리즘에 불리한 구조 (도달률 감소 요소 포함)

[글 비교 기준 — 이 차이로 채점하라]
나쁜 글 (tone=0, hook=0, angle=0):
"삼성전자가 파운드리 사업에서 대규모 투자를 발표했습니다. 이는 글로벌 반도체 시장에서 경쟁력을 강화하기 위한 전략으로 주목받고 있습니다."

좋은 글 (tone=15, hook=20, angle=15):
"삼성 파운드리 20조 베팅했는데 TSMC는 같은 날 40조 발표함. 근데 진짜 포인트는 돈이 아님. 삼성이 3나노 수율 50% 못 넘기고 있는 동안 TSMC는 2나노 양산 일정 확정. 돈으로 메울 수 있는 격차가 아닌 거임"

[판정 기준]
- tone = 0 (AI 어투 감지) → total 산정 후 reason에 검출된 AI 패턴 명시
- regulation ≤ 3 → 즉시 재생성 필요 (규제 위반은 계정에 치명적)
- total ≥ 70 → 통과, total < 70 → 재생성 권장
- 5개 트윗 중 3개 이상이 비슷한 시작/구조면 angle에서 최대 5점 감점

[JSON만 출력]
{"hook":N,"fact":N,"tone":N,"kick":N,"angle":N,"regulation":N,"algorithm":N,"total":N,"worst":"축이름","reason":"1줄 피드백 (AI 어투 검출 시 해당 표현 인용)"}"""


_QA_CLICHE_PATTERNS = (
    "주목받고 있다",
    "화제가 되고 있다",
    "관심이 쏠리고 있다",
    "다양한 의견이 있다",
    "알아보겠습니다",
    "분석해보면",
    "마무리하며",
    "결론적으로",
    "정리하면",
    "귀추가 주목된다",
    "여러분",
    "우리 모두",
)
_THREADS_BAIT_PATTERNS = ("좋아요", "댓글", "투표", "1)", "2)", "여러분의 생각")
_BLOG_REQUIRED_HEADINGS = (
    "## 왜 지금 중요한가",
    "## 무슨 신호가 보이나",
    "## 무엇을 봐야 하나",
    "## 핵심 정리",
)
_GENERIC_ENTITY_ALLOWLIST = {
    "ai", "x", "threads", "meta", "kbs", "sbs", "mbc", "jtbc", "bbc", "cnn",
    "wbc", "gpt", "it", "kst", "premium", "premium+",
}


def _build_allowed_fact_corpus(trend: ScoredTrend) -> str:
    parts = [
        getattr(trend, "top_insight", ""),
        getattr(trend, "why_trending", ""),
    ]
    if getattr(trend, "trend_context", None):
        parts.append(trend.trend_context.to_prompt_text())
    if getattr(trend, "context", None):
        parts.append(trend.context.to_combined_text())
    return "\n".join(p for p in parts if p)


def _extract_candidate_entities(text: str) -> set[str]:
    pattern = re.compile(
        r"[A-Z][A-Za-z0-9&.\-]{1,}|[가-힣A-Za-z0-9·]+(?:부|청|원|처|시|군|구|일보|뉴스|위원회|협회|센터|재단|법원|검찰|대학교|대학|공사|공단|은행|증권|그룹|시청|군청)"
    )
    return {match.group(0) for match in pattern.finditer(text)}


def _first_nonempty_lines(text: str, limit: int = 3) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()][:limit]


