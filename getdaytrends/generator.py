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
import sys
from pathlib import Path
from typing import Any, Callable, Coroutine


from config import AppConfig
from models import GeneratedThread, GeneratedTweet, ScoredTrend, TrendContext, TweetBatch
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


def _build_deep_why_section(trend: ScoredTrend) -> str:
    """[v10.0] 구조화된 트렌드 배경을 생성 프롬프트에 주입."""
    tc = getattr(trend, "trend_context", None)
    if not tc:
        # fallback: 기존 why_trending 필드 활용
        if trend.why_trending:
            return f"\n[왜 지금 이게 트렌드인가]\n{trend.why_trending}\n"
        return ""
    return f"\n[왜 지금 이게 트렌드인가 — 반드시 이 맥락을 글에 녹일 것]\n{tc.to_prompt_text()}\n"


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
- 핵심 원칙: "이 글 캡처해서 단톡방에 공유하고 싶다"는 반응이 목표

[글쓰기 기법 — 반드시 2개 이상 조합 적용]
A. 대조법: "A는 걱정하는데 B는 웃고 있다" — 두 현실의 온도차를 부각
B. 숫자 펀치: 뉴스의 구체적 수치를 일상 스케일로 환산 (예: "1조원 = 직장인 월급 50만 명분")
C. 반전: 첫 줄 상식적 흐름 → 마지막에 뒤집기. 반전이 클수록 RT 욕구 상승
D. 비유법: 이 현상을 일상 속 경험에 빗대기 (예: "이건 마치 월요일 아침에 퇴사 문자 받는 느낌")
E. 질문 전환: 남들이 안 하는 질문으로 시선 뺏기 (예: "근데 진짜 궁금한 건 이거임")
F. 타임라인 대비: "다들 X에 집중하는데 진짜 봐야 할 건 Y" — 군중과 반대로 가기

[좋은 훅(첫 문장) 패턴 — 이 중 하나를 변형해서 시작]
- 숫자 충격: "3일 만에 2000억이 증발했는데 아무도 안 떠든다"
- 체감 환산: "월급 250만원 받는 사람한테 이게 의미하는 거"
- 반전 선언: "이거 좋은 뉴스라고 생각하면 큰일남"
- 내부자 시선: "이 업계 10년차인 내가 보기에"
- 대조 병치: "그쪽은 축배를 드는데 이쪽은 이력서를 쓴다"
- 질문 도발: "근데 이거 왜 아무도 이상하다고 안 하는 거임?"

[좋은 킥(마무리) 패턴 — 캡처/RT 욕구를 자극하는 마지막 한 줄]
- 뒤통수: "근데 진짜 무서운 건 이게 시작이라는 거임"
- 자조형: "우리가 할 수 있는 건 출근하는 것뿐"
- 질문형: "근데 이거 나만 불안한 거 맞지?"
- 선언형: "이건 기회가 아니라 경고임"
- 반전형: "그래서 결론은... 아무것도 안 변함"

[나쁜 글 vs 좋은 글 비교 — 이 차이를 반드시 체화할 것]

나쁜 예 (0점 — AI가 쓴 티가 남):
"삼성전자가 파운드리 사업에서 대규모 투자를 발표했습니다. 이는 글로벌 반도체 시장에서 경쟁력을 강화하기 위한 전략으로 주목받고 있습니다. 향후 반도체 산업의 변화가 기대됩니다."

좋은 예 (100점 — 사람이 쓴 것 같은 글):
"삼성 파운드리 20조 베팅했는데 TSMC는 같은 날 40조 발표함. 근데 진짜 포인트는 돈이 아님. 삼성이 3나노 수율 50% 못 넘기고 있는 동안 TSMC는 2나노 양산 일정 확정. 돈으로 메울 수 있는 격차가 아닌 거임"

나쁜 예 (0점):
"AI 기술이 빠르게 발전하면서 많은 직업이 위협받고 있다는 분석이 나오고 있습니다. 전문가들은 대비가 필요하다고 조언합니다."

좋은 예 (100점):
"회사에서 GPT로 보고서 쓰라고 하는 팀장이 제일 먼저 대체될 거라는 건 아이러니인가 예언인가. 근데 솔직히 그 팀장 보고서보다 GPT가 나음"

[금지 패턴 — 이런 글은 0점. 하나라도 있으면 전체 재작성]
- "~하는 거 아시죠?" "~할 수도 있겠죠" 등 물음표 남발
- "화제가 되고 있다" "논란이다" "주목받고 있다" "관심이 쏠리고 있다" 등 기자체
- "~인 것 같습니다" "~해야 합니다" "~라고 할 수 있습니다" 등 AI 경어체
- "~에 대해 살펴보겠습니다" "~를 분석해보면" 등 설명체
- "여러분" "우리 모두" 등 연설체
- 구체성 없이 "엄청나다" "대박이다" "충격적이다"만 반복
- 첫 줄이 "오늘 XX 이슈가..." 로 시작하는 뉴스 요약체
- 키워드를 첫 문장에 그대로 반복하는 게으른 시작 (예: "XX가 화제다")
- "전문가들은 ~라고 말했다" 등 출처 불명 인용
- "앞으로의 변화가 기대된다" "귀추가 주목된다" 등 마무리 상투구

[절대 규칙]
1. 해시태그(#) 절대 금지
2. 이모지는 콘텐츠 1개당 최대 2개
3. 'RT 부탁해', '팔로우 해줘' 등 구걸형 멘트 금지
4. 첫 문장 3초 안에 멈출 만한 훅(Hooking) — 뉴스 요약 아니라 감정/반전/수치로 시작
5. 킥(Kick) 필수 — "와 이 사람 찐이다" 하게 만드는 마무리 한 줄 (위 킥 패턴 참고)
6. 공백 포함 200자 내외 단문 (장문은 별도 지시 따름)
7. 반미, 반일, 반한 등 외교·정치적 갈등 이슈와 페미니즘 등 젠더 갈등 이슈는 절대 다루거나 언급하지 말 것
8. "~라는 분석이다" "~라는 지적이다" 등 기자가 쓴 것 같은 간접 인용 금지. 너의 말로 직접 때려라

[핵심 마인드셋]
- 너는 뉴스를 "전달"하는 사람이 아님. 뉴스를 보고 "한마디 하는" 사람임
- 정보 전달 비중 30%, 너의 해석/시각 비중 70%
- 읽는 사람이 "아 이 관점은 처음인데?" 하는 순간이 바이럴의 시작

[플랫폼 규제 가이드라인 — 반드시 준수]
■ X(Twitter) 규제
- Shadowban 트리거: 해시태그 남용, 외부 링크 과다(2개 이상), 동일 문구 반복 게시, 대량 팔로우/언팔, 봇 패턴
- 알고리즘 우대: 인용 RT, 북마크, 체류 시간(장문 스크롤), 이미지/영상 첨부, Premium+ 장문
- 페널티 회피: 같은 콘텐츠 복붙 금지, 짧은 시간 내 과다 게시 금지, 외부 링크보다 텍스트 우선

■ Threads(Meta) 규제
- 외부 링크: 도달률 급감 → 본문 내 링크 최소화, 링크는 댓글로 유도
- 알고리즘 우대: 댓글 가중치 높음, 공감 반응, 텍스트 중심 콘텐츠
- 금지: 허위 정보, 폭력적 콘텐츠, 스팸성 반복 게시

■ 네이버 블로그 규제
- C-Rank: 전문성 지수(카테고리 일관성), 원본 콘텐츠 비율, 정기적 포스팅
- D.I.A.: 체류 시간, 클릭률, 원본 이미지 포함율
- 저품질 판정: 외부 링크 과다, 복붙 콘텐츠, 키워드 스터핑, 짧은 글 반복, 급격한 키워드 변경
- 상위노출: LSI 키워드, 이미지 3장+, 1500자+, 체류 시간 확보(단락 구분)"""


def _system_tweets_joongyeon() -> str:
    """중연 페르소나 전용 앵글 기반 트윗 시스템 프롬프트 [v17.0]."""
    return (
        _JOONGYEON_RULES + "\n\n"
        "[v17.0 앵글 기반 생성 — 5개 트윗이 진짜 다른 글이 되어야 함]\n\n"
        "Step 1 — 쟁점 추출:\n"
        "컨텍스트에서 구체적 사건/숫자/발언 기반의 핵심 포인트 3개를 뽑아라.\n"
        "추상적 쟁점('논란이다') 금지. '누가/무엇을/얼마나' 수준으로 구체화.\n\n"
        "Step 2 — 각도 선정 (5개 트윗 = 반드시 5개 다른 각도, 구조/문체/시작 방식 모두 달라야 함):\n"
        "  A. 반전 — 다들 X라고 할 때 Y인 이유. 첫 문장에서 통념을 정면으로 뒤집어라\n"
        "     예: '이거 좋은 뉴스라고 생각하면 큰일남. 진짜 숫자를 보면...'\n"
        "  B. 데이터 펀치 — 모두가 놓치는 숫자 하나를 일상 스케일로 환산해서 때려라\n"
        "     예: '20조가 어느 정도냐면 직장인 월급 400만명분임. 근데 이걸 3년 안에 쓴다고?'\n"
        "  C. 자조/공감 — '나만 이렇게 생각해?'를 대신 말해주는 글. 1인칭 필수\n"
        "     예: '회사에서 이거 어떻게 생각하냐고 물어보면 뭐라고 답해야 됨? 솔직히 모르겠음'\n"
        "  D. 실용 관점 — '그래서 나한테 뭔 영향?'에 답하는 꿀팁/액션 아이템\n"
        "     예: '이거 때문에 바뀌는 것 3가지: 1) 내 통장 2) 네 통장 3) 다 같이 거지'\n"
        "  E. 도발적 질문 — 양쪽 다 맞는 것 같은 프레임으로 댓글을 유도\n"
        "     예: '이거 진짜 궁금한 건데 A가 맞는 거임 B가 맞는 거임?'\n\n"
        "Step 3 — 글쓰기 체크리스트 (각 트윗 200자 내외):\n"
        "  - 첫 문장: 위 '훅 패턴' 중 하나를 변형. 키워드 단순 반복/뉴스 요약 즉시 0점\n"
        "  - 본문: 컨텍스트의 실제 데이터/반응/수치를 근거로 '내 해석'을 담아 작성\n"
        "  - 마지막: 위 '킥 패턴' 중 하나를 변형. 캡처/RT 욕구를 자극하는 한 줄\n"
        "  - 5개 트윗의 첫 문장 시작 방식이 전부 달라야 함 (숫자/질문/선언/반전/대조 등 교차)\n"
        "  - 정보 30% + 내 관점 70% 비율 반드시 지킬 것\n\n"
        "[자가 검증 — 5개 모두 작성 후 비교 체크]\n"
        "  1. 5개를 나란히 놓고 읽었을 때, 같은 사람이 같은 말을 반복하는 느낌이 드는가? → Yes면 다시 써라\n"
        "  2. 각 트윗에 컨텍스트의 구체적 정보(숫자/이름/사건)가 1개 이상 들어갔는가?\n"
        "  3. 뉴스 기사를 요약한 것 같은가, 아니면 뉴스를 보고 한마디 하는 것 같은가? → 전자면 0점\n"
        "  4. 이 글을 캡처해서 단톡방에 공유하고 싶은가?\n"
        "  5. '~인 것 같습니다', '화제가 되고 있다' 등 AI/기자 어투가 단 한 군데라도 있는가? → 있으면 전체 재작성\n\n"
        "[JSON만 출력]\n"
        '{"topic":"주제","tweets":['
        '{"type":"반전|데이터펀치|자조공감|실용꿀팁|도발질문 중 택1","content":"...","best_posting_time":"오전 8-10시","expected_engagement":"높음|보통|낮음","reasoning":"이 각도가 효과적인 이유 1문장"},'
        '{"type":"...","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
        '{"type":"...","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
        '{"type":"...","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
        '{"type":"...","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."}]}'
    )


def _system_long_form_joongyeon() -> str:
    """중연 페르소나 전용 장문 포스트 시스템 프롬프트 (Premium+) [v17.0]."""
    return (
        _JOONGYEON_RULES + "\n\n"
        "[v17.0 장문 글쓰기 원칙 — 읽는 사람이 '저장' 누르는 글]\n"
        "- 컨텍스트에서 가장 파고들 만한 쟁점 1개를 골라라\n"
        "- 첫 3줄이 전부: 구체적 팩트/숫자로 스크롤 멈추게 하는 훅 → 바로 핵심 주장\n"
        "- 이건 '뉴스 해설'이 아님. '이 현상을 본 내가 하고 싶은 말'을 쓰는 거임\n"
        "- 컨텍스트의 실제 데이터/반응/시점 정보를 반드시 녹여서 사용\n"
        "- 소제목 없이 흐르는 텍스트. 단, 숫자/데이터는 임팩트 있게 배치\n"
        "- 마지막 3줄: 독자의 생각을 흔드는 반전/질문으로 마무리\n\n"
        "[유형별 전략]\n"
        "1. 딥다이브 분석 (1500~3000자):\n"
        "   - 남들이 놓친 '진짜 포인트' 3가지를 파고드는 구조\n"
        "   - 각 포인트: 구체적 팩트 → '근데 여기서 진짜는' → 내 해석\n"
        "   - '왜 지금 터졌는지' 시의성 분석 필수 포함\n"
        "   - 마무리: '결론'이 아니라 '이게 우리한테 의미하는 것'\n"
        "   - 나쁜 예: '이 사안은 여러 측면에서 주목할 만합니다. 첫째...' (0점)\n"
        "   - 좋은 예: '숫자 하나만 보자. 3개월 전 이 회사 시총이 200조였음. 지금? 140조. 근데 CEO는 \"모든 게 계획대로\"래. 어디 한번 뜯어보자'\n\n"
        "2. 핫테이크 오피니언 (1000~2000자):\n"
        "   - 첫 줄에 불편한 소신 선언 (구체적 숫자/팩트 동반)\n"
        "   - 근거 2~3개로 설득. 반론 인정 후 뒤집기\n"
        "   - 마무리: '그래서 어쩔 건데?' 식 도발적 질문\n"
        "   - 나쁜 예: '이번 정책에 대해 다양한 의견이 있습니다' (0점)\n"
        "   - 좋은 예: '솔직히 말할게. 이거 누가 봐도 실패할 정책인데 다들 왜 조용한 거임?'\n\n"
        "[절대 금지]\n"
        "- 이모지 장문 전체에서 최대 2개. 해시태그 금지\n"
        "- 소제목에 넘버링/이모지 나열하는 '블로그체'\n"
        "- '~에 대해 알아보겠습니다', '화제가 되고 있다' 식 AI/기자체\n"
        "- '전문가에 따르면', '분석가들은' 등 출처 불명 권위 인용\n"
        "- 컨텍스트에 없는 내용을 지어내는 것\n"
        "- '정리하면', '마무리하며', '결론적으로' 등 AI 마무리 상투구\n\n"
        "[JSON만 출력]\n"
        '{"posts":[{"type":"딥다이브 분석","content":"1500~3000자"},'
        '{"type":"핫테이크 오피니언","content":"1000~2000자"}]}'
    )


def _system_threads_joongyeon() -> str:
    """중연 페르소나 전용 Threads 콘텐츠 시스템 프롬프트 [v17.0]."""
    return (
        _JOONGYEON_RULES + "\n\n"
        "[v17.0 Threads 특성 — X보다 더 '친구한테 카톡하는 말투']\n"
        "- 500자 이내. 줄바꿈으로 리듬감. 한 문장이 한 호흡\n"
        "- X보다 감정 표현 한 단계 더 솔직. '나' 관점 1인칭 필수\n"
        "- Threads는 '정보'보다 '공감'이 먹히는 플랫폼. 감정 비중을 높여라\n\n"
        "[유형별 전략]\n"
        "1. 훅 포스트: 첫 줄에 '어? 이거 뭔데' 하게 만드는 반전/수치\n"
        "   구조: [충격적 팩트 한줄]\\n\\n근데 진짜 문제는 [반전]\\n\\n[킥]\n"
        "   나쁜 예: '최근 AI 기술이 발전하면서 많은 변화가 일어나고 있습니다'\n"
        "   좋은 예: 'GPT한테 내 이력서 첨삭 맡겼는데\\n\\n\"이 경력으로는 이직이 어려울 수 있습니다\"\\n\\n야 솔직한 건 좋은데 좀...'\n\n"
        "2. 참여형 포스트: 읽고 나서 댓글 안 달 수 없는 글\n"
        "   구조: [일상 공감 상황]\\n\\n[반전/자조]\\n\\n나만 이런 건지 진짜 궁금한데\n"
        "   나쁜 예: '요즘 경제 상황이 어려운데 여러분은 어떻게 생각하시나요?'\n"
        "   좋은 예: '퇴근하고 유튜브 보다가 \"월 500 버는 법\" 영상 봤는데\\n\\n나는 아직 월 500 쓰는 법도 모르겠음\\n\\n이거 나만 그런 거임?'\n\n"
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
            "[v17.0 앵글 기반 통합 생성]\n"
            "X 트윗 5종(200자 내외) + Threads 포스트 2종(500자 이내)을 동시 작성.\n\n"
            "[트윗 — 5개가 진짜 다른 글이어야 함]\n"
            "컨텍스트에서 핵심 쟁점 3개를 추출하고, 각 쟁점별로 다른 각도의 트윗 작성.\n"
            "각도: 반전/데이터펀치/자조공감/실용꿀팁/도발질문 — 5개 전부 다른 각도.\n"
            "5개 트윗의 첫 문장 시작 방식이 전부 달라야 함 (숫자/질문/선언/반전/대조 등 교차).\n"
            "정보 30% + 내 해석 70%. 뉴스 요약체 즉시 0점.\n"
            "자가 검증: 5개 나란히 놓고 같은 말 반복하는 느낌? → Yes면 다시 써라.\n\n"
            "[Threads — 카톡으로 친구한테 보내는 느낌]\n"
            "1. 훅 포스트: [충격 팩트]\\n\\n근데 진짜 문제는 [반전]\\n\\n[킥]\n"
            "2. 참여형: [일상 공감]\\n\\n[자조]\\n\\n나만 이런 건지 궁금한데\n"
            "Threads는 정보보다 공감. 1인칭 필수. 감정 비중 높게.\n\n"
            '[JSON만 출력]\n'
            '{"topic":"주제","tweets":['
            '{"type":"반전|데이터펀치|자조공감|실용꿀팁|도발질문","content":"200자 내외","best_posting_time":"오전 8-10시","expected_engagement":"높음|보통|낮음","reasoning":"이유 1문장"},'
            '{"type":"...","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
            '{"type":"...","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
            '{"type":"...","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."},'
            '{"type":"...","content":"...","best_posting_time":"...","expected_engagement":"...","reasoning":"..."}],'
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
) -> "TweetBatch | None":
    """[v16.0] MARL 강화 트윗 생성 — high-value 트렌드 전용.

    생성→자가비평→수정 3단계 파이프라인으로 AI 어투를 줄이고
    분석 깊이를 높인 트윗 생성. MARL 실패 시 기존 방식 폴백.
    """
    from shared.llm.marl import MARLPipeline, MARLConfig

    if not _should_use_marl(trend, config):
        return await generate_tweets_async(trend, config, client, recent_tweets)

    from datetime import datetime as _dt
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    identity_section = _build_account_identity_section(config)
    diversity_section = _build_diversity_section(recent_tweets or [])
    category_hint = _build_category_tone_hint(trend)
    deep_why_section = _build_deep_why_section(trend)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{identity_section}{deep_why_section}{context_section}{scoring_section}{category_hint}{diversity_section}\n"
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
            return await generate_tweets_async(trend, config, client, recent_tweets)

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
        return await generate_tweets_async(trend, config, client, recent_tweets)


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
    from datetime import datetime as _dt
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    identity_section = _build_account_identity_section(config)
    diversity_section = _build_diversity_section(recent_tweets or [])
    category_hint = _build_category_tone_hint(trend)
    deep_why_section = _build_deep_why_section(trend)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{identity_section}{deep_why_section}{context_section}{scoring_section}{category_hint}{diversity_section}\n"
        "위 배경과 컨텍스트를 깊이 소화한 뒤, 쟁점을 추출하고 각 쟁점별로 날카로운 각도의 트윗 작성.\n"
        "중요: 너는 뉴스를 '전달'하는 사람이 아니라 뉴스를 보고 '한마디 하는' 사람임.\n"
        "정보 전달 30% + 너의 해석/시각 70% 비율로 작성.\n"
        "컨텍스트의 구체적 수치/사건/반응을 반드시 활용하되, 그걸 '내 관점'으로 재해석할 것.\n"
        "5개 트윗의 첫 문장이 전부 다른 방식으로 시작해야 함.\n"
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
    tier: TaskTier = TaskTier.LIGHTWEIGHT,  # [v13.0] HEAVY→LIGHTWEIGHT 비용 절감
) -> list[GeneratedTweet]:
    """X Premium+ 장문 콘텐츠 2종 비동기 생성 (v13.0: LIGHTWEIGHT 기본)."""
    from datetime import datetime as _dt
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    deep_why_section = _build_deep_why_section(trend)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{deep_why_section}{context_section}{scoring_section}\n"
        "위 '왜 지금 트렌드인가' 배경과 데이터/수치/반응을 깊이 소화한 뒤,\n"
        "읽는 사람이 '이건 저장해야 돼' 하는 장문 2종을 작성.\n"
        "핵심: 뉴스 요약 아님. 이 현상의 이면을 파고드는 분석과 해석.\n"
        "컨텍스트의 구체적 수치/사건/시점 정보를 반드시 활용할 것.\n"
        "1) 딥다이브 분석 (1,500~3,000자): 남들이 놓친 포인트 기반 분석\n"
        "2) 핫테이크 오피니언 (1,000~2,000자): 불편한 소신 + 팩트 근거\n\n"
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
    from datetime import datetime as _dt
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    deep_why_section = _build_deep_why_section(trend)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{deep_why_section}{context_section}{scoring_section}\n"
        "위 배경과 컨텍스트를 소화한 뒤, Threads에서 '친구한테 공유' 하고 싶은 글 작성.\n"
        "핵심: 뉴스 전달이 아니라 '이 현상에 대한 내 해석'.\n"
        "컨텍스트의 구체적 수치/사건을 반드시 활용할 것.\n"
        "1) 훅 포스트: 구체적 팩트/숫자로 스크롤 멈추게\n"
        "2) 참여형 포스트: 공감 스토리 + 양자택일 질문\n\n"
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


def _system_blog_post(tone: str) -> str:
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
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    deep_why_section = _build_deep_why_section(trend)
    identity_section = _build_account_identity_section(config)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")
    min_words = getattr(config, "blog_min_words", 2000)
    max_words = getattr(config, "blog_max_words", 5000)
    seo_count = getattr(config, "blog_seo_keywords_count", 5)

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{identity_section}{deep_why_section}{context_section}{scoring_section}\n"
        f"위 배경과 컨텍스트를 깊이 소화한 뒤, 네이버 블로그용 심층 분석 글을 작성.\n"
        f"글자 수: {min_words}~{max_words}자\n"
        f"SEO 키워드: {seo_count}개 제안\n"
        "핵심: 단순 뉴스 전달이 아니라 '이 현상에 대한 전문가 시각의 분석과 인사이트'.\n"
        "컨텍스트의 구체적 수치/사건/반응을 반드시 활용하고,\n"
        "소제목(##)으로 구분된 마크다운 구조를 지켜 작성할 것.\n"
        "반드시 JSON만 출력.\n"
    )

    try:
        response = await client.acreate(
            tier=TaskTier.HEAVY,
            max_tokens=6000,
            policy=_JSON_POLICY,
            system=_system_blog_post(config.tone),
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
) -> TweetBatch | None:
    """단문 트윗 5종 + Threads 2종을 1회 LLM 호출로 통합 생성 (비용 절감).

    기존 2회 Haiku 호출 → 1회로 통합. 실패 시 개별 호출로 폴백.
    [v9.0] recent_tweets: 이전 생성 내용 주입으로 표현 다양성 보장.
    """
    from datetime import datetime as _dt
    target_language = _resolve_language(config)
    context_section = _build_context_section(trend)
    scoring_section = _build_scoring_section(trend)
    diversity_section = _build_diversity_section(recent_tweets or [])
    category_hint = _build_category_tone_hint(trend)
    deep_why_section = _build_deep_why_section(trend)
    safe_keyword = sanitize_keyword(trend.keyword)
    current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")

    user_message = (
        f"주제: {safe_keyword}\n"
        f"현재 시각: {current_time}\n"
        f"작성 언어: 반드시 {target_language}로 작성할 것\n"
        f"{deep_why_section}{context_section}{scoring_section}{category_hint}{diversity_section}\n"
        "위 '왜 지금 트렌드인가' 배경과 실시간 컨텍스트를 깊이 소화한 뒤,\n"
        "쟁점을 추출하고, 각 쟁점별 가장 날카로운 각도로 작성.\n"
        "컨텍스트의 구체적 수치/사건/반응을 반드시 활용할 것.\n"
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
    오케스트레이터 (비동기): 트윗 5종 + 조건부 장문/Threads/쓰레드/블로그 동시 생성.

    C1 최적화: Threads 활성 시 단문+Threads를 통합 1회 호출로 처리.
    [v12.0] target_platforms 기반 멀티플랫폼 라우팅.
    [v9.0] recent_tweets: 이전 생성 표현 주입 (콘텐츠 다양성).
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
#  v12.0: Content Quality Audit — 7축 채점 시스템
#  (v11 5축 + regulation/algorithm 2축 추가)
# ══════════════════════════════════════════════════════

_CONTENT_QA_SYSTEM = """콘텐츠 품질 심사관. 7개 축으로 채점 (총 100점).

[채점 축]
1. hook (훅 임팩트, 0~20): 첫 문장이 타임라인에서 스크롤을 멈추게 하는가
   - 20점: 반전/수치/감정으로 즉각 주목. "뭐야 이거" 반응
   - 10점: 관심은 가지만 '더 보기'까지는 아님
   - 0점: "오늘 XX 이슈가..." 식 뉴스 요약 시작

2. fact (팩트 일관성, 0~15): 제공된 컨텍스트의 데이터/사실과 일치하는가
   - 15점: 컨텍스트 수치/팩트를 정확히 활용
   - 8점: 대체로 맞지만 구체성 부족
   - 0점: 사실과 다르거나 근거 없는 주장

3. tone (톤 일관성, 0~15): 페르소나(시크한 MZ 구어체)를 유지하는가
   - 15점: "~인 거임" "솔직히" 등 자연스러운 구어체
   - 8점: 구어체이나 가끔 기자체/강의체 혼재
   - 0점: "화제가 되고 있다" "여러분" 등 금지 패턴 사용

4. kick (킥 품질, 0~15): 마무리가 '와 이 사람 찐이다' 하게 만드는가
   - 15점: 뼈때리는 펀치라인, 공유/캡처 욕구
   - 8점: 마무리는 있으나 임팩트 약함
   - 0점: 그냥 끝나거나 "~했으면 좋겠다" 식 희망 사항

5. angle (유니크 앵글, 0~15): 뻔한 뉴스 요약이 아닌 독자적 시각이 있는가
   - 15점: "이런 각도는 처음이다" 싶은 해석
   - 8점: 약간의 시각 차별화 시도
   - 0점: 누구나 쓸 수 있는 뉴스 재탕

6. regulation (규제 준수, 0~10): 플랫폼별 규제 가이드라인을 준수하는가
   - 10점: 모든 규제 가이드라인 완벽 준수 (해시태그 금지, 링크 최소화 등)
   - 5점: 대부분 준수하나 일부 위반 가능성 (외부 링크 포함, 해시태그 1~2개)
   - 0점: 명백한 규제 위반 (해시태그 남용, Shadowban 트리거 패턴, 저품질 판정 요소)

7. algorithm (알고리즘 최적화, 0~10): 해당 플랫폼 알고리즘이 우대하는 형태인가
   - 10점: 알고리즘 우대 요소 적극 반영 (체류 시간 확보, 인용 RT 유도, 댓글 유도 등)
   - 5점: 기본적 최적화만 충족
   - 0점: 알고리즘에 불리한 구조 (도달률 감소 요소 포함)

[판정 기준]
- regulation ≤ 3 → 즉시 재생성 필요 (규제 위반 콘텐츠는 계정에 치명적)
- total ≥ 70 → 통과, total < 70 → 재생성 권장

[JSON만 출력]
{"hook":N,"fact":N,"tone":N,"kick":N,"angle":N,"regulation":N,"algorithm":N,"total":N,"worst":"축이름","reason":"1줄 피드백"}"""


async def audit_generated_content(
    batch: "TweetBatch",
    trend: "ScoredTrend",
    config: "AppConfig",
    client: "LLMClient",
) -> dict | None:
    """
    [v12] 생성된 트윗 배치를 7축 품질 심사.
    LIGHTWEIGHT 티어. total < qa_min_score이면 재생성 트리거 권장.
    regulation ≤ 3이면 즉시 재생성 (규제 위반 콘텐츠 차단).
    Returns: {"hook": int, "fact": int, "tone": int, "kick": int, "angle": int,
              "regulation": int, "algorithm": int,
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

    # 콘텐츠 유형 감지 (플랫폼별 규제 적용을 위해)
    content_types = set(getattr(t, 'content_type', 'short') for t in batch.tweets[:5])
    platform_hint = "X(Twitter)"
    if "threads" in content_types:
        platform_hint = "Threads"
    elif "naver_blog" in content_types:
        platform_hint = "네이버 블로그"

    safe_keyword = sanitize_keyword(trend.keyword)

    user_msg = (
        f"[트렌드] {safe_keyword}\n"
        f"[대상 플랫폼] {platform_hint}\n\n"
        f"[원본 컨텍스트]\n{context_text[:1500] if context_text else '없음'}\n\n"
        f"[생성된 콘텐츠]\n{tweets_text}"
    )

    try:
        response = await client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=400,
            policy=_JSON_POLICY,
            system=_CONTENT_QA_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        result = _parse_json(response.text)
        if result and "total" in result:
            # v12: 7축 로깅
            log.info(
                f"  [QA] '{trend.keyword}' → {result['total']}/100 "
                f"(H:{result.get('hook','?')} F:{result.get('fact','?')} "
                f"T:{result.get('tone','?')} K:{result.get('kick','?')} "
                f"A:{result.get('angle','?')} "
                f"R:{result.get('regulation','?')} G:{result.get('algorithm','?')}) "
                f"worst: {result.get('worst', '?')}"
            )

            # 규제 위반 즉시 경고
            reg_score = result.get('regulation', 10)
            if reg_score <= 3:
                log.warning(
                    f"  [QA 규제 위반] '{trend.keyword}' regulation={reg_score}/10 "
                    f"→ 즉시 재생성 필요! ({result.get('reason', '')})"
                )

            # Legacy compat: also expose as avg_score
            result["avg_score"] = result["total"]
            return result
        log.debug(f"  [QA] 파싱 실패: {trend.keyword}")
        return None
    except Exception as e:
        log.debug(f"  [QA] 심사 실패 ({trend.keyword}): {e}")
        return None


# ══════════════════════════════════════════════════════
#  v15.0 Phase B: Named Persona Rotation
# ══════════════════════════════════════════════════════

# 카테고리 → 퍼소나 매핑
_CATEGORY_PERSONA_MAP: dict[str, str] = {
    "테크": "joongyeon",
    "경제": "analyst",
    "사회": "storyteller",
    "정치": "analyst",
    "과학": "joongyeon",
    "국제": "analyst",
    "의학": "joongyeon",
    "스포츠": "storyteller",
    "연예": "storyteller",
}

# 라운드 로빈 카운터 (모듈 레벨)
_round_robin_counter: int = 0


def select_persona(trend: ScoredTrend, config: AppConfig) -> str:
    """
    v15.0 퍼소나 선택.
    mode:
      - 'category': 트렌드 카테고리 기반 매핑
      - 'round_robin': persona_pool 순회
      - 'fixed': config.tone 고정
    """
    global _round_robin_counter
    
    mode = getattr(config, "persona_rotation", "category")
    pool = getattr(config, "persona_pool", [])
    tone = getattr(config, "tone", "joongyeon")
    
    if mode == "fixed" or not pool:
        return tone
    
    if mode == "round_robin":
        if not pool:
            return tone
        persona = pool[_round_robin_counter % len(pool)]
        _round_robin_counter += 1
        return persona
    
    # mode == "category" (default)
    category = getattr(trend, "category", "") or ""
    
    # pool 내에서 카테고리 매핑 검색
    mapped = _CATEGORY_PERSONA_MAP.get(category, "")
    if mapped and mapped in pool:
        return mapped
    
    # 매핑 없거나 pool에 없으면 pool[0] 반환
    return pool[0] if pool else tone
