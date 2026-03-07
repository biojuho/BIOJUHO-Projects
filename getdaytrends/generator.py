"""
getdaytrends v3.0 - Tweet & Thread & Long-form & Threads Generation
컨텍스트 기반 트윗 3종 + X Premium+ 장문 + Meta Threads 3종 + 강화 쓰레드 3개.
async/await 기반 병렬 생성 + JSON structured output 지원.

v3.0 변경:
- _retry_generate: 지수 백오프 재시도 래퍼 (2회, 1s→3s)
- generate_ab_variant_async: A/B 변형 생성 (tone 다양화)
- _step_generate_multilang: 멀티언어 루프 (target_languages 순회)
- 모든 async 함수에 반환 타입 힌트 추가
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Callable, Coroutine

# shared.llm 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import AppConfig
from models import GeneratedThread, GeneratedTweet, ScoredTrend, TweetBatch
from shared.llm import LLMClient, TaskTier
from shared.llm.models import LLMPolicy
from utils import sanitize_keyword

from loguru import logger as log

_JSON_POLICY = LLMPolicy(response_mode="json")

# ── 언어 코드 매핑 ────────────────────────────────────
_LANG_NAME_MAP: dict[str, str] = {
    "ko": "한국어", "en": "영어", "ja": "일본어",
    "es": "스페인어", "fr": "프랑스어", "zh": "중국어",
}


# ══════════════════════════════════════════════════════
#  Retry Helper (Phase 1)
# ══════════════════════════════════════════════════════

async def _retry_generate(
    coro_factory: Callable[[], Coroutine[Any, Any, Any]],
    keyword: str,
    max_retries: int = 2,
    base_delay: float = 1.0,
) -> Any:
    """
    생성 코루틴을 지수 백오프로 재시도.
    coro_factory: 호출할 때마다 새 코루틴을 반환하는 람다.
    예: _retry_generate(lambda: generate_tweets_async(trend, cfg, client), trend.keyword)
    """
    for attempt in range(max_retries + 1):
        try:
            result = await coro_factory()
            if result is not None:
                return result
        except Exception as e:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                log.warning(
                    f"생성 재시도 ({attempt + 1}/{max_retries}) '{keyword}': "
                    f"{type(e).__name__} → {delay:.0f}s 후"
                )
                await asyncio.sleep(delay)
            else:
                log.error(f"생성 최종 실패 '{keyword}': {e}")
    return None


# ══════════════════════════════════════════════════════
#  Category-based Tier Routing (Phase 4)
# ══════════════════════════════════════════════════════

def _select_generation_tier(trend: ScoredTrend, config: AppConfig) -> "TaskTier":
    """카테고리 기반 LLM 티어 결정.

    heavy_categories(정치/경제/테크 등)는 Sonnet(HEAVY) 유지.
    연예/스포츠/날씨 등 경량 카테고리는 Haiku(LIGHTWEIGHT)로 다운그레이드.
    카테고리 미분류(category="")는 안전하게 HEAVY 유지.
    """
    category = getattr(trend, "category", "") or ""
    if not category:
        return TaskTier.HEAVY  # 카테고리 불명 → 기존 동작 유지

    heavy_cats = config.heavy_categories
    for heavy_cat in heavy_cats:
        if heavy_cat in category:
            return TaskTier.HEAVY

    return TaskTier.LIGHTWEIGHT


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
    """
    다국어 자율 트랜스크리에이션 기초 설정:
    TARGET_LANGUAGES 환경변수가 단일 언어면 그대로 반환.
    여러 언어일 경우 (예: ko, en, ja) 콤마로 결합하여 LLM에 전달.
    추후 (v2.6) _step_generate에서 언어별로 루프를 도는 구조로 확장 가능.
    """
    if config.target_languages and config.target_languages != ["ko"]:
        # "ko", "en" 등 다국어 식별자가 들어있을 때
        # 향후에는 이 리스트를 순회하며 개별 TweetBatch를 생성하는 구조적 확장이 필요함 (기반 마련)
        mapping = {"ko": "한국어", "en": "영어", "ja": "일본어", "es": "스페인어", "fr": "프랑스어"}
        langs = [mapping.get(l.lower(), l) for l in config.target_languages]
        return ", ".join(langs)
    
    return _LANGUAGE_MAP.get((config.country or "").lower(), "한국어(Korean)")


def _build_account_identity_section(config: AppConfig) -> str:
    """[v8.0] 프롬프트 ②: 계정 정체성 섹션 생성."""
    niche = getattr(config, "account_niche", "")
    audience = getattr(config, "target_audience", "")
    if not niche and not audience:
        return ""
    parts = []
    if niche:
        parts.append(f"- 분야: {niche}")
    parts.append(f"- 톤앤매너: {config.tone}")
    if audience:
        parts.append(f"- 타겟 오디언스: {audience}")
    return "\n[계정 정체성]\n" + "\n".join(parts) + "\n"


def _build_diversity_section(recent_tweets: list[str]) -> str:
    """[v9.0] 이전 생성 트윗 목록을 프롬프트에 주입해 표현 중복 방지."""
    if not recent_tweets:
        return ""
    previews = "\n".join(f"  - {t[:80]}..." if len(t) > 80 else f"  - {t}" for t in recent_tweets[:4])
    return f"\n[이미 생성된 표현 — 반드시 다른 각도/어휘로 작성할 것]\n{previews}\n"


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


def _build_category_tone_hint(trend: ScoredTrend) -> str:
    """[v11] 카테고리별 글쓰기 기법 우선순위 힌트."""
    category = getattr(trend, "category", "") or ""
    hints = {
        "정치": "기법 우선: 대조법 + 반전. 팩트 기반으로만 때릴 것",
        "경제": "기법 우선: 숫자 강조 + 비유법. 체감 가능한 비유로 풀어줄 것",
        "테크": "기법 우선: 비유법 + 질문 전환. 비전공자도 '오' 하게 설명",
        "사회": "기법 우선: 공감 + 반전. 개인 일상과 연결",
        "스포츠": "기법 우선: 숫자 강조 + 대조법. 기록/통계로 임팩트",
    }
    hint = hints.get(category, "")
    return f"\n[카테고리 톤 힌트: {category}]\n{hint}\n" if hint else ""


# ══════════════════════════════════════════════════════
#  JSON Parser
# ══════════════════════════════════════════════════════

def _parse_json(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return None


# ══════════════════════════════════════════════════════
#  System Prompt Builders  (tone 주입 — P1-2)
# ══════════════════════════════════════════════════════

# ── 중연 페르소나 전용 프롬프트 ─────────────────────────

_JOONGYEON_RULES = """당신은 X(구 트위터) 인플루언서 '중연'입니다.

[정체성]
- 20~30대 직장인의 속마음을 대신 말해주는 사람
- 뉴스를 보면 남들이 놓치는 '진짜 포인트'를 짚어냄
- 과장은 싫지만 뼈때리는 건 좋아함. 팩트로 때림
- 말투: "~인 거임", "~아닌가", "근데 진짜", "솔직히" 등 MZ 구어체

[글쓰기 기법 — 반드시 1개 이상 적용]
- 대조법: "A는 걱정하는데 B는 웃고 있다"
- 숫자 강조: 뉴스에 나온 구체적 수치를 임팩트 있게 배치
- 반전: 첫 줄에서 상식적 흐름 → 마지막에 뒤집기
- 비유법: 이 현상을 일상 속 다른 것에 빗대기
- 질문 전환: 남들이 안 하는 질문으로 시선 뺏기

[금지 패턴 — 이런 글은 0점임]
- "~하는 거 아시죠?" "~할 수도 있겠죠" 등 물음표 남발
- "화제가 되고 있다" "논란이다" 등 기자체 표현
- "여러분" "우리 모두" 등 연설체
- 구체성 없이 "엄청나다" "대박이다" "충격적이다"만 반복
- 첫 줄이 "오늘 XX 이슈가..." 로 시작하는 뉴스 요약체

[절대 규칙]
1. 해시태그(#) 절대 금지
2. 이모지는 콘텐츠 1개당 최대 2개
3. 'RT 부탁해', '팔로우 해줘' 등 구걸형 멘트 금지
4. 첫 문장 3초 안에 멈출 만한 훅(Hooking) — 뉴스 요약 아니라 감정/반전/수치로 시작
5. 킥(Kick) 필수 — "와 이 사람 찐이다" 하게 만드는 마무리 한 줄
6. 공백 포함 200자 내외 단문 (장문은 별도 지시 따름)"""


def _system_tweets_joongyeon() -> str:
    """중연 페르소나 전용 단문 트윗 5종 시스템 프롬프트."""
    return (
        _JOONGYEON_RULES + "\n\n"
        "5가지 유형의 트윗을 작성. 각각 완전히 다른 톤과 앵글이어야 함:\n\n"
        "1. 공감 유도형: 읽는 사람이 '아 진짜 이거ㅋㅋ' 하며 캡처할 만한 글.\n"
        "   기법: 내 일상 속 경험을 대입 → 마지막에 뼈때리는 한 줄\n"
        "   예시 패턴: '[상황] 하고 있는 나. [반전/자조]'\n\n"
        "2. 꿀팁형: '이거 몰랐으면 손해볼 뻔' 느낌의 실용 정보.\n"
        "   기법: 구체적 숫자/방법 → '근데 대부분 이거 모름'\n"
        "   예시 패턴: '[팩트/수치]. 근데 진짜 중요한 건 [숨겨진 포인트]'\n\n"
        "3. 찬반 질문형: 양쪽 다 맞는 것 같아서 댓글 안 달 수 없는 질문.\n"
        "   기법: 극단적 양자택일 or '이게 맞다고?' 식 도발\n"
        "   예시 패턴: '[A] vs [B], 솔직히 뭐가 맞는 건지'\n\n"
        "4. 시크한 관찰형: 남들이 안 보는 각도에서 한 방에 정리.\n"
        "   기법: 대조법/비유법으로 핵심을 비틀어 표현\n"
        "   예시 패턴: '[현상]인 줄 알았는데 알고 보면 [반전 해석]'\n\n"
        "5. 핫테이크형: '와 이 사람 용감하다' 싶은 소신 발언.\n"
        "   기법: 불편한 진실 + 근거 1개로 설득력 확보\n"
        "   예시 패턴: '솔직히 [논쟁적 의견]. [데이터/팩트 1개]'\n\n"
        "[JSON만 출력]\n"
        '{"topic":"주제","tweets":['
        '{"type":"공감 유도형","content":"...","best_posting_time":"오전 8-10시","expected_engagement":"높음|보통|낮음","reasoning":"효과적인 이유 1문장"},'
        '{"type":"꿀팁형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
        '{"type":"찬반 질문형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
        '{"type":"시크한 관찰형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
        '{"type":"핫테이크형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."}]}'
    )


def _system_long_form_joongyeon() -> str:
    """중연 페르소나 전용 장문 포스트 시스템 프롬프트 (Premium+)."""
    return (
        _JOONGYEON_RULES + "\n\n"
        "[장문 글쓰기 원칙]\n"
        "- 첫 3줄이 전부: 스크롤 멈추게 하는 훅 → 바로 핵심 주장\n"
        "- '뉴스 기사 같은 설명'이 아니라 '내 분석/해석'이 담긴 글\n"
        "- 소제목 없이 흐르는 텍스트. 단, 숫자/데이터는 강조 배치\n"
        "- 마지막 3줄: 독자의 생각을 흔드는 반전/질문으로 마무리\n\n"
        "[유형별 전략]\n"
        "1. 딥다이브 시리즈 (1500~3000자):\n"
        "   - 남들이 놓친 '진짜 포인트' 3가지를 파고드는 구조\n"
        "   - 각 포인트마다: 팩트 → 해석 → '근데 여기서 진짜 중요한 건'\n"
        "   - 마무리: '결론'이 아니라 '이게 의미하는 것'\n\n"
        "2. 핫테이크 오피니언 (1000~2000자):\n"
        "   - 첫 줄에 불편한 소신 선언. 바로 때리기\n"
        "   - 근거 2~3개로 설득하되 반론도 인정\n"
        "   - 마무리: '그래서 어쩔 건데?' 식 도발적 질문\n\n"
        "[절대 금지]\n"
        "- 이모지 장문 전체에서 최대 2개. 해시태그 금지\n"
        "- 소제목에 넘버링/이모지 나열하는 '블로그체'\n"
        "- '~에 대해 알아보겠습니다' 식 강의체\n\n"
        "[JSON만 출력]\n"
        '{"posts":[{"type":"딥다이브 시리즈","content":"1500~3000자"},'
        '{"type":"핫테이크 오피니언","content":"1000~2000자"}]}'
    )


def _system_threads_joongyeon() -> str:
    """중연 페르소나 전용 Threads 콘텐츠 시스템 프롬프트."""
    return (
        _JOONGYEON_RULES + "\n\n"
        "[Threads 특성 — X보다 더 '친구한테 하는 말']\n"
        "- 500자 이내. 줄바꿈으로 리듬감. 한 문장이 한 호흡\n"
        "- X보다 감정 표현 한 단계 더 솔직. '나' 관점 필수\n\n"
        "[유형별 전략]\n"
        "1. 훅 포스트: 첫 줄에 '어? 이거 뭔데' 하게 만드는 반전/수치\n"
        "   기법: 상식 뒤집기 or 충격적 숫자로 시작\n"
        "   예시 패턴: '[충격적 팩트 한줄].\\n\\n근데 진짜 문제는 [반전]'\n\n"
        "2. 참여형 포스트: 읽고 나서 댓글 안 달 수 없는 글\n"
        "   기법: 공감 스토리 → 마지막에 양자택일 질문\n"
        "   예시 패턴: '[공감 상황].\\n\\n나만 이런 건지 진짜 궁금한데'\n\n"
        "[JSON만 출력]\n"
        '{"posts":[{"type":"훅 포스트","content":"500자 이내"},'
        '{"type":"참여형 포스트","content":"500자 이내"}]}'
    )


# ── 기존 프롬프트 빌더 (tone 분기 포함) ──────────────────

def _system_tweets(tone: str) -> str:
    if tone == "joongyeon":
        return _system_tweets_joongyeon()
    return (
        f"X 트렌드 카피라이터. 말투: {tone}\n"
        "답글 유도하는 280자(한글 140자) 이내 트윗 작성. 공감/밈/질문/데이터 활용.\n"
        "첫 문장에 훅 필수. 고유한 시각·인사이트를 담을 것. 감정적 과장·낚시성 표현 금지.\n\n"
        '[JSON만 출력]\n'
        '{"topic":"주제","tweets":['
        '{"type":"공감 유도형","content":"...","best_posting_time":"오전 8-10시","expected_engagement":"높음|보통|낮음","reasoning":"효과적인 이유 1문장"},'
        '{"type":"꿀팁형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
        '{"type":"찬반 질문형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
        '{"type":"동기부여형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
        '{"type":"유머/밈형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."}]}'
    )


def _system_long_form(tone: str) -> str:
    if tone == "joongyeon":
        return _system_long_form_joongyeon()
    return (
        f"X Premium+ 장문 작가. 말투: {tone}\n"
        "이모지 소제목+번호 구조, 데이터 인용, 반직관적 해석, 강렬한 훅, CTA 마무리.\n\n"
        '[JSON만 출력]\n'
        '{"posts":[{"type":"딥다이브 분석","content":"1500~2500자"},'
        '{"type":"핫테이크 오피니언","content":"1000~2000자"}]}'
    )


def _system_threads(tone: str) -> str:
    if tone == "joongyeon":
        return _system_threads_joongyeon()
    return (
        f"Meta Threads 크리에이터. 말투: {tone}(더 캐주얼).\n"
        "500자 이내. 이모지+줄바꿈 적극사용. 친구 톤.\n\n"
        '[JSON만 출력]\n'
        '{"posts":[{"type":"훅 포스트","content":"500자 이내"},'
        '{"type":"참여형 포스트","content":"500자 이내"}]}'
    )


def _system_thread(tone: str) -> str:
    if tone == "joongyeon":
        return (
            _JOONGYEON_RULES + "\n\n"
            "[X 쓰레드 전략]\n"
            "정확히 2개 트윗으로 구성된 바이럴 쓰레드.\n\n"
            "1번 트윗 (훅, ~2500자):\n"
            "   - 첫 2줄: 타임라인에서 '더 보기' 누르게 하는 훅\n"
            "   - 본문: 남들이 안 하는 각도로 주제를 파고드는 분석\n"
            "   - 데이터/수치를 임팩트 있게 배치. '근데 진짜는' 전환\n\n"
            "2번 트윗 (마무리, 500~1000자):\n"
            "   - '그래서 뭐?'에 대한 답. 실용적 인사이트 or 도발적 결론\n"
            "   - 마지막 줄: RT하고 싶게 만드는 킥 한 줄\n\n"
            "[금지] 해시태그 절대 금지. 이모지 전체 최대 2개\n\n"
            '[JSON만 출력]\n'
            '{"hook":"첫 트윗","tweets":["훅","마무리"]}'
        )
    return (
        f"X 바이럴 쓰레드 전문가. 말투: {tone}\n"
        "정확히 2개 트윗. 훅(~2500자)+마무리CTA(500~1000자). 데이터 인용.\n\n"
        '[JSON만 출력]\n'
        '{"hook":"첫 트윗","tweets":["훅","마무리 CTA"]}'
    )


def _system_tweets_and_threads(tone: str) -> str:
    """단문 트윗 5종 + Threads 2종을 한 번에 생성하는 통합 시스템 프롬프트."""
    if tone == "joongyeon":
        return (
            _JOONGYEON_RULES + "\n\n"
            "X 트윗 5종(200자 내외)과 Threads 포스트 2종(500자 이내)을 동시 작성.\n\n"
            "[트윗 유형별 가이드]\n"
            "1. 공감 유도형: '아 진짜 이거ㅋㅋ' 하며 캡처. 일상 대입 → 뼈때리기\n"
            "2. 꿀팁형: '몰랐으면 손해' 실용 정보. 숫자/방법 → '근데 대부분 이거 모름'\n"
            "3. 찬반 질문형: 양쪽 다 맞아서 댓글 불가피. 극단적 양자택일/도발\n"
            "4. 시크한 관찰형: 남들이 안 보는 각도. 대조법/비유법으로 비틀기\n"
            "5. 핫테이크형: 용감한 소신. 불편한 진실 + 근거 1개\n\n"
            '[JSON만 출력]\n'
            '{"topic":"주제","tweets":['
            '{"type":"공감 유도형","content":"200자 내외","best_posting_time":"오전 8-10시","expected_engagement":"높음|보통|낮음","reasoning":"효과적인 이유 1문장"},'
            '{"type":"꿀팁형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
            '{"type":"찬반 질문형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
            '{"type":"시크한 관찰형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
            '{"type":"핫테이크형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."}],'
            '"threads_posts":['
            '{"type":"훅 포스트","content":"500자 이내"},'
            '{"type":"참여형 포스트","content":"500자 이내"}]}'
        )
    return (
        f"X+Threads 콘텐츠 크리에이터. 말투: {tone}\n"
        "한 주제에 대해 X 트윗 5종(280자)과 Threads 포스트 2종(500자)을 동시 작성.\n\n"
        '[JSON만 출력]\n'
        '{"topic":"주제","tweets":['
        '{"type":"공감 유도형","content":"280자 이내","best_posting_time":"오전 8-10시","expected_engagement":"높음|보통|낮음","reasoning":"효과적인 이유 1문장"},'
        '{"type":"꿀팁형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
        '{"type":"찬반 질문형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
        '{"type":"동기부여형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
        '{"type":"유머/밈형","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."}],'
        '"threads_posts":['
        '{"type":"훅 포스트","content":"500자 이내"},'
        '{"type":"참여형 포스트","content":"500자 이내"}]}'
    )


# ══════════════════════════════════════════════════════
#  1) 단문 트윗 5종 (280자) — Haiku tier
# ══════════════════════════════════════════════════════

async def generate_tweets_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None = None,
) -> TweetBatch | None:
    """5종 단문 트윗 비동기 생성 (Haiku — 비용 절감).
    [v9.0] recent_tweets: 이전 생성 내용 주입으로 표현 다양성 보장.
    """
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    identity_section = _build_account_identity_section(config)
    diversity_section = _build_diversity_section(recent_tweets or [])
    category_hint = _build_category_tone_hint(trend)
    safe_keyword = sanitize_keyword(trend.keyword)

    user_message = (
        f"주제: {safe_keyword}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{identity_section}{context_section}{scoring_section}{category_hint}{diversity_section}\n"
        "위 컨텍스트와 분석 데이터를 깊이 소화한 뒤,\n"
        "각 트윗이 타임라인에서 '멈추고 읽게 만드는' 콘텐츠가 되도록 작성.\n"
        "핵심: 뉴스 요약이 아니라 '내 생각/시각'이 담긴 글.\n"
        "반드시 JSON만 출력."
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

    except Exception as e:
        log.error(f"트윗 생성 실패 ({trend.keyword}): {e}")
        return None


# ══════════════════════════════════════════════════════
#  2) X Premium+ 장문 포스트 (1,500~3,000자) — Sonnet tier
# ══════════════════════════════════════════════════════

async def generate_long_form_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    tier: TaskTier = TaskTier.HEAVY,
) -> list[GeneratedTweet]:
    """X Premium+ 장문 콘텐츠 2종 비동기 생성 (기본 Sonnet, 경량 카테고리는 Haiku)."""
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    safe_keyword = sanitize_keyword(trend.keyword)

    user_message = (
        f"주제: {safe_keyword}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{context_section}{scoring_section}\n"
        "위 컨텍스트의 데이터/수치/반응을 깊이 소화한 뒤,\n"
        "읽는 사람이 '이건 저장해야 돼' 하는 장문 2종을 작성.\n"
        "핵심: 뉴스 요약 아님. 당신만의 분석과 해석이 담긴 글.\n"
        "1) 딥다이브 분석 (1,500~2,500자): 데이터 기반 구조화된 분석\n"
        "2) 핫테이크 오피니언 (1,000~2,000자): 논쟁적이고 감정을 자극하는 의견\n\n"
        "반드시 JSON만 출력하세요."
    )

    try:
        response = await client.acreate(
            tier=tier,
            max_tokens=4000,
            policy=_JSON_POLICY,
            system=_system_long_form(config.tone),
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
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    safe_keyword = sanitize_keyword(trend.keyword)

    user_message = (
        f"주제: {safe_keyword}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{context_section}{scoring_section}\n"
        "위 컨텍스트를 소화한 뒤, Threads에서 '친구한테 공유' 하고 싶은 글 작성.\n"
        "핵심: 뉴스 전달이 아니라 '이 주제에 대한 내 생각'.\n"
        "1) 훅 포스트: 타임라인에서 스크롤을 멈추게 하는 강렬한 도입\n"
        "2) 참여형 포스트: 공감 + 질문으로 댓글 유도\n\n"
        "각 포스트 500자 이내. 반드시 JSON만 출력하세요."
    )

    try:
        response = await client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=1200,
            policy=_JSON_POLICY,
            system=_system_threads(config.tone),
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
) -> TweetBatch | None:
    """단문 트윗 5종 + Threads 2종을 1회 LLM 호출로 통합 생성 (비용 절감).

    기존 2회 Haiku 호출 → 1회로 통합. 실패 시 개별 호출로 폴백.
    [v9.0] recent_tweets: 이전 생성 내용 주입으로 표현 다양성 보장.
    """
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    diversity_section = _build_diversity_section(recent_tweets or [])
    category_hint = _build_category_tone_hint(trend)
    safe_keyword = sanitize_keyword(trend.keyword)

    user_message = (
        f"주제: {safe_keyword}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{context_section}{scoring_section}{category_hint}{diversity_section}\n"
        "위 컨텍스트를 깊이 소화한 뒤, 타임라인에서 멈추고 읽게 만들 콘텐츠 작성.\n"
        "핵심: 뉴스 요약이 아니라 '내 생각/시각'이 담긴 글.\n"
        "X 트윗 5종(각 200자 내외) + Threads 포스트 2종(각 500자 이내).\n"
        "반드시 JSON만 출력."
    )

    try:
        response = await client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=2200,
            policy=_JSON_POLICY,
            system=_system_tweets_and_threads(config.tone),
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json(response.text)

        if not data or "tweets" not in data:
            log.warning(f"통합 생성 파싱 실패, 개별 생성 폴백: {trend.keyword}")
            return None

        # 단문 트윗 파싱
        tweets = []
        for t in data.get("tweets", []):
            content = t.get("content", "")
            if len(content) > 280:
                content = content[:277] + "..."
                log.warning(f"트윗 280자 초과 트리밍: {trend.keyword}")
            tweets.append(GeneratedTweet(
                tweet_type=t.get("type", ""),
                content=content,
                content_type="short",
                best_posting_time=t.get("best_posting_time", ""),
                expected_engagement=t.get("expected_engagement", ""),
                reasoning=t.get("reasoning", ""),
            ))

        # Threads 포스트 파싱
        threads_posts = [
            GeneratedTweet(
                tweet_type=p.get("type", "Threads"),
                content=p.get("content", ""),
                content_type="threads",
            )
            for p in data.get("threads_posts", [])
        ]

        log.info(f"통합 생성 완료: '{trend.keyword}' (트윗 {len(tweets)}개 + Threads {len(threads_posts)}개)")
        return TweetBatch(
            topic=data.get("topic", trend.keyword),
            tweets=tweets,
            threads_posts=threads_posts,
            viral_score=trend.viral_potential,
        )

    except Exception as e:
        log.error(f"통합 생성 실패 ({trend.keyword}): {e}")
        return None


# ══════════════════════════════════════════════════════
#  Async Orchestrator — 트렌드 내 모든 생성 병렬 실행
# ══════════════════════════════════════════════════════

async def generate_for_trend_async(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
    recent_tweets: list[str] | None = None,
) -> TweetBatch | None:
    """
    오케스트레이터 (비동기): 트윗 5종 + 조건부 장문/Threads/쓰레드 동시 생성.

    C1 최적화: Threads 활성 시 단문+Threads를 통합 1회 호출로 처리.
    LLM 호출 수: 기존 ~4회/트렌드 → ~2~3회/트렌드.
    [v9.0] recent_tweets: 이전 생성 표현 주입 (콘텐츠 다양성).
    """
    # Phase 4: 카테고리 기반 티어 결정
    gen_tier = _select_generation_tier(trend, config)
    category = getattr(trend, "category", "") or "미분류"
    tier_label = "Sonnet" if gen_tier == TaskTier.HEAVY else "Haiku↓"

    # Threads 활성 여부 확인
    threads_enabled = config.enable_threads and trend.viral_potential >= config.threads_min_score

    # C3: 생성 티어 표시 (비용 투명성)
    tier_parts = ["단문(5종)" + ("+Threads(통합)" if threads_enabled else "")]
    if config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
        tier_parts.append(f"Premium+장문({tier_label})")
    if trend.viral_potential >= config.thread_min_score:
        tier_parts.append(f"X쓰레드({tier_label})")
    log.info(f"  [{trend.viral_potential}점/{category}] '{trend.keyword}' → {' + '.join(tier_parts)}")

    tasks: dict[str, asyncio.Task] = {}

    # C1 최적화: Threads 가능하면 통합 호출, 아니면 기존 개별 호출
    if threads_enabled:
        tasks["combined"] = asyncio.ensure_future(
            generate_tweets_and_threads_async(trend, config, client, recent_tweets)
        )
    else:
        tasks["tweets"] = asyncio.ensure_future(
            generate_tweets_async(trend, config, client, recent_tweets)
        )

    if config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
        tasks["long"] = asyncio.ensure_future(generate_long_form_async(trend, config, client, tier=gen_tier))

    if trend.viral_potential >= config.thread_min_score:
        tasks["thread"] = asyncio.ensure_future(generate_thread_async(trend, config, client, tier=gen_tier))

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
                generate_tweets_async(trend, config, client),
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

    return batch


def generate_for_trend(
    trend: ScoredTrend,
    config: AppConfig,
    client: LLMClient,
) -> TweetBatch | None:
    """동기 래퍼 (하위 호환)."""
    return asyncio.run(generate_for_trend_async(trend, config, client))


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
    if not config.enable_multilang or len(config.target_languages) <= 1:
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
#  v11.0: Content Quality Audit — 5축 채점 시스템
# ══════════════════════════════════════════════════════

_CONTENT_QA_SYSTEM = """콘텐츠 품질 심사관. 5개 축으로 0~20점씩 채점 (총 100점).

[채점 축]
1. hook (훅 임팩트): 첫 문장이 타임라인에서 스크롤을 멈추게 하는가
   - 20점: 반전/수치/감정으로 즉각 주목. "뭐야 이거" 반응
   - 10점: 관심은 가지만 '더 보기'까지는 아님
   - 0점: "오늘 XX 이슈가..." 식 뉴스 요약 시작

2. fact (팩트 일관성): 제공된 컨텍스트의 데이터/사실과 일치하는가
   - 20점: 컨텍스트 수치/팩트를 정확히 활용
   - 10점: 대체로 맞지만 구체성 부족
   - 0점: 사실과 다르거나 근거 없는 주장

3. tone (톤 일관성): 페르소나(시크한 MZ 구어체)를 유지하는가
   - 20점: "~인 거임" "솔직히" 등 자연스러운 구어체
   - 10점: 구어체이나 가끔 기자체/강의체 혼재
   - 0점: "화제가 되고 있다" "여러분" 등 금지 패턴 사용

4. kick (킥 품질): 마무리가 '와 이 사람 찐이다' 하게 만드는가
   - 20점: 뼈때리는 펀치라인, 공유/캡처 욕구
   - 10점: 마무리는 있으나 임팩트 약함
   - 0점: 그냥 끝나거나 "~했으면 좋겠다" 식 희망 사항

5. angle (유니크 앵글): 뻔한 뉴스 요약이 아닌 독자적 시각이 있는가
   - 20점: "이런 각도는 처음이다" 싶은 해석
   - 10점: 약간의 시각 차별화 시도
   - 0점: 누구나 쓸 수 있는 뉴스 재탕

[JSON만 출력]
{"hook":N,"fact":N,"tone":N,"kick":N,"angle":N,"total":N,"worst":"축이름","reason":"1줄 피드백"}"""


async def audit_generated_content(
    batch: "TweetBatch",
    trend: "ScoredTrend",
    config: "AppConfig",
    client: "LLMClient",
) -> dict | None:
    """
    [v11] 생성된 트윗 배치를 5축 품질 심사.
    LIGHTWEIGHT 티어. total < qa_min_score이면 재생성 트리거 권장.
    Returns: {"hook": int, "fact": int, "tone": int, "kick": int, "angle": int,
              "total": int, "worst": str, "reason": str} or None.
    """
    if not batch or not batch.tweets:
        return None

    tweets_text = "\n".join(
        f"[{t.tweet_type}] {t.content}" for t in batch.tweets[:5]
    )
    context_text = ""
    if trend.context:
        context_text = trend.context.to_combined_text() or ""

    safe_keyword = sanitize_keyword(trend.keyword)

    user_msg = (
        f"[트렌드] {safe_keyword}\n\n"
        f"[원본 컨텍스트]\n{context_text[:1500] if context_text else '없음'}\n\n"
        f"[생성된 콘텐츠]\n{tweets_text}"
    )

    try:
        response = await client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=300,
            policy=_JSON_POLICY,
            system=_CONTENT_QA_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        result = _parse_json(response.text)
        if result and "total" in result:
            log.info(
                f"  [QA] '{trend.keyword}' → {result['total']}/100 "
                f"(H:{result.get('hook','?')} F:{result.get('fact','?')} "
                f"T:{result.get('tone','?')} K:{result.get('kick','?')} "
                f"A:{result.get('angle','?')}) "
                f"worst: {result.get('worst', '?')}"
            )
            # Legacy compat: also expose as avg_score
            result["avg_score"] = result["total"]
            return result
        log.debug(f"  [QA] 파싱 실패: {trend.keyword}")
        return None
    except Exception as e:
        log.debug(f"  [QA] 심사 실패 ({trend.keyword}): {e}")
        return None

