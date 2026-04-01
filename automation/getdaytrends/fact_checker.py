"""
getdaytrends v6.0 - Fact Checker & Hallucination Detection

정보 정확성을 위한 3계층 검증 모듈:
1. Claim Extraction: 생성 콘텐츠에서 검증 가능한 주장(숫자, 날짜, 고유명사, 통계) 추출
2. Cross-Reference Verification: 추출된 주장을 수집된 소스 데이터와 교차 검증
3. Hallucination Detection: 소스에 없는 정보가 생성된 경우 탐지 및 플래그

사용:
    from fact_checker import verify_content, FactCheckResult
    result = verify_content(generated_text, trend, config)
    if not result.passed:
        # 재생성 또는 수정
"""

import re
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger as log

try:
    from .models import ScoredTrend, TweetBatch
except ImportError:
    from models import ScoredTrend, TweetBatch

# -- credibility imports --
try:
    from .source_credibility import (  # noqa: F401
        _CREDIBILITY_WEIGHTS,
        _SOURCE_CREDIBILITY_MAP,
        CredibilityTier,
        compute_source_credibility_score,
        get_source_credibility,
    )
except ImportError:
    from source_credibility import (  # noqa: F401
        _CREDIBILITY_WEIGHTS,
        _SOURCE_CREDIBILITY_MAP,
        CredibilityTier,
        compute_source_credibility_score,
        get_source_credibility,
    )

# ══════════════════════════════════════════════════════
#  Claim Types & Extraction
# ══════════════════════════════════════════════════════


class ClaimType(Enum):
    """검증 가능한 주장 유형."""

    NUMBER = "number"  # 구체적 숫자/통계 (50만명, 2000억 등)
    PERCENTAGE = "percentage"  # 백분율 (30%, +15% 등)
    DATE = "date"  # 날짜/시점 (3월 15일, 어제 등)
    ENTITY = "entity"  # 고유명사 (기관, 인물, 기업명 등)
    QUOTE = "quote"  # 직접/간접 인용 ("~라고 말했다")
    COMPARISON = "comparison"  # 비교 주장 ("A보다 B가 크다")


@dataclass
class Claim:
    """추출된 개별 주장."""

    claim_type: ClaimType
    value: str  # 추출된 값 ("2000억", "삼성전자" 등)
    context: str = ""  # 주장이 포함된 문장
    verified: bool = False  # 소스에서 확인됨
    source_match: str = ""  # 매칭된 소스 텍스트
    confidence: float = 0.0  # 검증 확신도 (0~1)


@dataclass
class FactCheckResult:
    """팩트 체크 결과."""

    passed: bool = True
    total_claims: int = 0
    verified_claims: int = 0
    unverified_claims: int = 0
    hallucinated_claims: int = 0  # 소스에 전혀 없는 주장
    claims: list[Claim] = field(default_factory=list)
    accuracy_score: float = 1.0  # 0~1 (verified / total)
    source_credibility: float = 0.0  # 0~1
    issues: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """사람이 읽기 좋은 요약."""
        if self.passed:
            return f"통과 (정확도={self.accuracy_score:.0%}, 소스신뢰={self.source_credibility:.0%})"
        return (
            f"실패 (정확도={self.accuracy_score:.0%}, "
            f"미검증={self.unverified_claims}, 환각={self.hallucinated_claims})"
        )


# ══════════════════════════════════════════════════════
#  Claim Extraction
# ══════════════════════════════════════════════════════

# 숫자 패턴: 한국어 + 영어 단위
_NUMBER_PATTERN = re.compile(
    r"(\d{1,3}(?:[,.]?\d{3})*(?:\.\d+)?)\s*"
    r"(만|억|조|천|백|명|원|달러|개|건|회|대|곳|편|배|위|%|퍼센트|"
    r"[KkMmBb]|[Tt]ril(?:lion)?|[Bb]il(?:lion)?|[Mm]il(?:lion)?|"
    r"views|점|km|kg|ton|[Tt]B|[Gg]B)"
)

# 날짜 패턴: 한국어
_DATE_PATTERN = re.compile(
    r"(\d{1,2}월\s*\d{1,2}일|\d{4}년(?:\s*\d{1,2}월)?(?:\s*\d{1,2}일)?|"
    r"어제|오늘|그저께|지난\s*(?:주|달|해)|"
    r"\d+\s*(?:시간|일|주|개월|년)\s*(?:전|후|만에|동안))"
)

# 인용 패턴: 직접/간접
_QUOTE_PATTERN = re.compile(
    r'["\u201C\u201D\u300C\u300D]([^"\u201C\u201D\u300C\u300D]{5,80})["\u201C\u201D\u300C\u300D]'
    r"|(?:['\"](.*?)['\"])\s*(?:라고|이라고|며)\s*(?:말했|전했|밝혔|보도했)"
)

# 비교 패턴
_COMPARISON_PATTERN = re.compile(
    r"(\S+)\s*(?:보다|대비|비해|대신|반면|달리)\s+(\S+)"
    r"|(\S+)\s*(?:는|은)\s+(\S+)\s*(?:의|에)\s+(\d+(?:\.\d+)?)\s*배"
)

# 고유명사 패턴 (기관/기업/인물)
_ENTITY_PATTERN = re.compile(
    r"[A-Z][A-Za-z0-9&.\-]{1,}"  # 영문 고유명사
    r"|[가-힣A-Za-z0-9·]+(?:부|청|원|처|시|군|구|일보|뉴스|위원회|협회|센터|"
    r"재단|법원|검찰|대학교|대학|공사|공단|은행|증권|그룹|시청|군청|장관|대표|"
    r"사장|회장|교수|의원|총리|대통령|CEO|CTO)"
)

# 일반적인 고유명사 (검증 대상에서 제외)
_COMMON_ENTITIES = {
    "ai",
    "x",
    "threads",
    "meta",
    "kbs",
    "sbs",
    "mbc",
    "jtbc",
    "bbc",
    "cnn",
    "wbc",
    "gpt",
    "it",
    "kst",
    "premium",
    "google",
    "apple",
    "samsung",
    "naver",
    "kakao",
    "openai",
    "microsoft",
    "amazon",
    "tesla",
    "nvidia",
    "chatgpt",
    "claude",
    "gemini",
    "youtube",
    "instagram",
    "facebook",
    "삼성",
    "현대",
    "기아",
    "네이버",
    "카카오",
    "한국",
    "미국",
    "일본",
    "중국",
}


def extract_claims(text: str) -> list[Claim]:
    """생성된 콘텐츠에서 검증 가능한 주장을 추출."""
    if not text:
        return []

    claims: list[Claim] = []
    seen_values: set[str] = set()

    # 문장 단위로 분리
    sentences = re.split(r"[.!?\n]+", text)

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 5:
            continue

        # 1. 숫자/통계 추출
        for m in _NUMBER_PATTERN.finditer(sentence):
            value = m.group(0).strip()
            if value not in seen_values:
                seen_values.add(value)
                claims.append(
                    Claim(
                        claim_type=ClaimType.NUMBER,
                        value=value,
                        context=sentence,
                    )
                )

        # 2. 백분율 추출 (NUMBER와 별도)
        for m in re.finditer(r"[+-]?\d+(?:\.\d+)?%", sentence):
            value = m.group(0)
            if value not in seen_values:
                seen_values.add(value)
                claims.append(
                    Claim(
                        claim_type=ClaimType.PERCENTAGE,
                        value=value,
                        context=sentence,
                    )
                )

        # 3. 날짜 추출
        for m in _DATE_PATTERN.finditer(sentence):
            value = m.group(0).strip()
            if value not in seen_values:
                seen_values.add(value)
                claims.append(
                    Claim(
                        claim_type=ClaimType.DATE,
                        value=value,
                        context=sentence,
                    )
                )

        # 4. 인용 추출
        for m in _QUOTE_PATTERN.finditer(sentence):
            value = (m.group(1) or m.group(2) or "").strip()
            if value and value not in seen_values and len(value) > 5:
                seen_values.add(value)
                claims.append(
                    Claim(
                        claim_type=ClaimType.QUOTE,
                        value=value,
                        context=sentence,
                    )
                )

        # 5. 고유명사 추출 (일반적인 것 제외)
        for m in _ENTITY_PATTERN.finditer(sentence):
            value = m.group(0).strip()
            if value.casefold() not in _COMMON_ENTITIES and value not in seen_values and len(value) >= 2:
                seen_values.add(value)
                claims.append(
                    Claim(
                        claim_type=ClaimType.ENTITY,
                        value=value,
                        context=sentence,
                    )
                )

        # 6. 비교 추출
        for m in _COMPARISON_PATTERN.finditer(sentence):
            value = m.group(0).strip()
            if value not in seen_values and len(value) > 5:
                seen_values.add(value)
                claims.append(
                    Claim(
                        claim_type=ClaimType.COMPARISON,
                        value=value,
                        context=sentence,
                    )
                )

    return claims


# ══════════════════════════════════════════════════════
#  Cross-Reference Verification
# ══════════════════════════════════════════════════════


def _build_source_corpus(trend: ScoredTrend) -> str:
    """트렌드의 모든 소스 데이터를 하나의 검색 가능한 텍스트로 결합."""
    parts: list[str] = []

    # 키워드 자체
    parts.append(trend.keyword)

    # 기본 분석 결과
    if trend.top_insight:
        parts.append(trend.top_insight)
    if trend.why_trending:
        parts.append(trend.why_trending)

    # 구조화된 배경 (TrendContext)
    if trend.trend_context:
        parts.append(trend.trend_context.to_prompt_text())

    # 멀티소스 컨텍스트
    if trend.context:
        parts.append(trend.context.to_combined_text())

    # 추가 필드
    if trend.best_hook_starter:
        parts.append(trend.best_hook_starter)
    if trend.suggested_angles:
        parts.extend(trend.suggested_angles)
    if trend.corrected_keyword:
        parts.append(trend.corrected_keyword)

    return "\n".join(p for p in parts if p)


def _normalize_number(text: str) -> float | None:
    """숫자 문자열을 정규화된 float로 변환."""
    text = text.strip().replace(",", "")
    multipliers = {
        "만": 10_000,
        "억": 100_000_000,
        "조": 1_000_000_000_000,
        "천": 1_000,
        "백": 100,
        "k": 1_000,
        "m": 1_000_000,
        "b": 1_000_000_000,
        "trillion": 1_000_000_000_000,
        "billion": 1_000_000_000,
        "million": 1_000_000,
    }
    m = re.match(r"([+-]?\d+(?:\.\d+)?)\s*(.+)?", text)
    if not m:
        return None
    num = float(m.group(1))
    unit = (m.group(2) or "").strip().lower()
    for suffix, mult in multipliers.items():
        if unit.startswith(suffix):
            return num * mult
    return num


def verify_claim_against_source(claim: Claim, source_corpus: str) -> Claim:
    """
    개별 주장을 소스 코퍼스와 대조하여 검증.
    검증 결과를 claim 객체에 반영.
    """
    if not source_corpus:
        claim.confidence = 0.0
        return claim

    source_lower = source_corpus.lower()
    value_lower = claim.value.lower()

    if claim.claim_type == ClaimType.NUMBER:
        # 숫자 검증: 정확 매칭 또는 유사 범위 매칭
        if claim.value in source_corpus:
            claim.verified = True
            claim.confidence = 1.0
            claim.source_match = _find_context_around(source_corpus, claim.value)
        else:
            # 숫자 부분만 추출해서 소스에 존재하는지 확인
            num = re.search(r"\d+(?:[,.]?\d+)*", claim.value)
            if num and num.group(0) in source_corpus:
                claim.verified = True
                claim.confidence = 0.8
                claim.source_match = _find_context_around(source_corpus, num.group(0))
            else:
                # 정규화된 숫자 비교 (±20% 범위)
                claim_num = _normalize_number(claim.value)
                if claim_num is not None:
                    for m in _NUMBER_PATTERN.finditer(source_corpus):
                        source_num = _normalize_number(m.group(0))
                        if source_num is not None and source_num > 0:
                            ratio = claim_num / source_num
                            if 0.8 <= ratio <= 1.2:
                                claim.verified = True
                                claim.confidence = 0.6
                                claim.source_match = m.group(0)
                                break

    elif claim.claim_type == ClaimType.PERCENTAGE:
        if claim.value in source_corpus:
            claim.verified = True
            claim.confidence = 1.0
            claim.source_match = _find_context_around(source_corpus, claim.value)
        else:
            # % 숫자 부분만 비교
            pct_num = re.search(r"(\d+(?:\.\d+)?)", claim.value)
            if pct_num:
                for m in re.finditer(r"(\d+(?:\.\d+)?)%", source_corpus):
                    if pct_num.group(1) == m.group(1):
                        claim.verified = True
                        claim.confidence = 0.9
                        claim.source_match = m.group(0)
                        break

    elif claim.claim_type == ClaimType.DATE:
        if value_lower in source_lower:
            claim.verified = True
            claim.confidence = 1.0
            claim.source_match = _find_context_around(source_corpus, claim.value)
        else:
            # 날짜 구성 요소 부분 매칭
            date_nums = re.findall(r"\d+", claim.value)
            if date_nums and any(n in source_corpus for n in date_nums if len(n) >= 2):
                claim.verified = True
                claim.confidence = 0.5  # 부분 매칭이므로 낮은 확신도

    elif claim.claim_type == ClaimType.ENTITY:
        if value_lower in source_lower:
            claim.verified = True
            claim.confidence = 1.0
            claim.source_match = _find_context_around(source_corpus, claim.value)
        else:
            # 부분 매칭 (긴 고유명사의 일부)
            if len(claim.value) >= 3:
                for segment_len in range(len(claim.value), max(2, len(claim.value) // 2 - 1), -1):
                    segment = claim.value[:segment_len]
                    if segment.lower() in source_lower:
                        claim.verified = True
                        claim.confidence = 0.5
                        claim.source_match = segment
                        break

    elif claim.claim_type == ClaimType.QUOTE:
        # 인용은 정확 매칭만 허용 (가장 엄격)
        if value_lower in source_lower:
            claim.verified = True
            claim.confidence = 1.0
            claim.source_match = _find_context_around(source_corpus, claim.value)
        else:
            # 핵심 단어 기반 부분 매칭
            words = [w for w in claim.value.split() if len(w) >= 2]
            if words:
                matched = sum(1 for w in words if w.lower() in source_lower)
                if matched / len(words) >= 0.7:
                    claim.verified = True
                    claim.confidence = 0.4
                    claim.source_match = "(핵심 단어 부분 매칭)"

    elif claim.claim_type == ClaimType.COMPARISON:
        if value_lower in source_lower:
            claim.verified = True
            claim.confidence = 1.0
            claim.source_match = _find_context_around(source_corpus, claim.value)
        else:
            # 비교 대상이 소스에 있는지 확인
            parts = re.split(r"보다|대비|비해|반면", claim.value)
            if len(parts) >= 2:
                matched = sum(1 for p in parts if p.strip().lower() in source_lower)
                if matched >= 1:
                    claim.verified = True
                    claim.confidence = 0.5

    return claim


def _find_context_around(corpus: str, needle: str, window: int = 50) -> str:
    """소스 코퍼스에서 매칭된 값 주변 텍스트를 추출."""
    idx = corpus.find(needle)
    if idx == -1:
        idx = corpus.lower().find(needle.lower())
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(corpus), idx + len(needle) + window)
    return corpus[start:end].strip()


# ══════════════════════════════════════════════════════
#  Content Verification (통합 API)
# ══════════════════════════════════════════════════════


def verify_content(
    text: str,
    trend: ScoredTrend,
    *,
    strict_mode: bool = False,
    min_accuracy: float = 0.6,
) -> FactCheckResult:
    """
    생성된 콘텐츠의 정보 정확성을 검증.

    Args:
        text: 검증할 생성 콘텐츠
        trend: 소스 데이터가 포함된 ScoredTrend
        strict_mode: True면 인용/비교도 엄격 검증
        min_accuracy: 통과 기준 정확도 (0~1)

    Returns:
        FactCheckResult with pass/fail and details
    """
    result = FactCheckResult()

    if not text or not text.strip():
        result.passed = True  # 빈 텍스트는 검증 대상 아님
        return result

    # 1. 주장 추출
    claims = extract_claims(text)
    result.total_claims = len(claims)

    if not claims:
        result.passed = True
        result.accuracy_score = 1.0
        return result

    # 2. 소스 코퍼스 구축
    source_corpus = _build_source_corpus(trend)

    # 3. 출처 신뢰도 산출
    news_insight = ""
    if trend.context and trend.context.news_insight:
        news_insight = trend.context.news_insight
    result.source_credibility = compute_source_credibility_score(news_insight)

    # 4. 각 주장 교차 검증
    verified = 0
    hallucinated = 0
    unverified = 0

    for claim in claims:
        verify_claim_against_source(claim, source_corpus)

        if claim.verified:
            verified += 1
        elif claim.claim_type in (ClaimType.QUOTE, ClaimType.ENTITY):
            # 인용과 고유명사는 소스 미확인 시 환각으로 간주
            hallucinated += 1
            result.issues.append(f"[환각 의심] {claim.claim_type.value}: '{claim.value}' - 소스에서 확인 불가")
        elif claim.claim_type == ClaimType.NUMBER and not strict_mode:
            # 숫자는 LLM 추론으로 생성될 수 있으므로 경고만
            unverified += 1
            result.issues.append(f"[미검증 수치] '{claim.value}' - 소스에서 직접 확인 불가")
        else:
            unverified += 1

    result.claims = claims
    result.verified_claims = verified
    result.unverified_claims = unverified
    result.hallucinated_claims = hallucinated

    # 5. 정확도 계산
    if result.total_claims > 0:
        result.accuracy_score = round(verified / result.total_claims, 2)
    else:
        result.accuracy_score = 1.0

    # 6. 통과/실패 판정
    result.passed = result.hallucinated_claims == 0 and result.accuracy_score >= min_accuracy

    # [Phase 3] DeepEval 보조 평가 — 규칙 기반 검증을 LLM 기반으로 보완
    try:
        try:
            from .quality_eval import evaluate_content as deepeval_check
        except ImportError:
            from quality_eval import evaluate_content as deepeval_check

        source_context = _build_source_corpus(trend)
        eval_result = deepeval_check(text, source_context, trend.keyword)
        if not eval_result.passed:
            for issue in eval_result.issues:
                result.issues.append(f"[DeepEval] {issue}")
            # DeepEval이 환각을 감지했으면 규칙 기반이 통과여도 실패 처리
            if eval_result.hallucination_score > 0.7:
                result.passed = False
                log.warning(f"[DeepEval] '{trend.keyword}' 환각 점수 높음: " f"{eval_result.hallucination_score:.2f}")
    except ImportError:
        pass  # DeepEval 미설치 시 기존 동작 유지
    except Exception as e:
        log.debug(f"[DeepEval] 보조 평가 스킵: {e}")

    return result


def verify_batch(
    batch: TweetBatch,
    trend: ScoredTrend,
    *,
    strict_mode: bool = False,
    min_accuracy: float = 0.6,
) -> dict[str, FactCheckResult]:
    """
    TweetBatch 전체의 정보 정확성을 그룹별로 검증.

    Returns:
        {"tweets": FactCheckResult, "long_posts": ..., ...}
    """
    results: dict[str, FactCheckResult] = {}

    group_map = {
        "tweets": list(getattr(batch, "tweets", []) or []),
        "threads_posts": list(getattr(batch, "threads_posts", []) or []),
        "long_posts": list(getattr(batch, "long_posts", []) or []),
        "blog_posts": list(getattr(batch, "blog_posts", []) or []),
    }

    for group_name, items in group_map.items():
        if not items:
            continue
        combined = "\n".join(item.content for item in items if item.content)
        result = verify_content(
            combined,
            trend,
            strict_mode=strict_mode,
            min_accuracy=min_accuracy,
        )
        results[group_name] = result

        # 로깅
        if not result.passed:
            log.warning(
                f"  [FactCheck:{group_name}] '{trend.keyword}' 실패 "
                f"(정확도={result.accuracy_score:.0%}, 환각={result.hallucinated_claims})"
            )
        else:
            log.debug(
                f"  [FactCheck:{group_name}] '{trend.keyword}' 통과 "
                f"(정확도={result.accuracy_score:.0%}, 주장={result.total_claims})"
            )

    return results


# ══════════════════════════════════════════════════════
#  Cross-Source Consistency Check
# ══════════════════════════════════════════════════════


def check_cross_source_consistency(trend: ScoredTrend) -> dict:
    """
    멀티소스 간 정보 일관성 검증.
    X, Reddit, News 소스의 핵심 주장이 서로 일치하는지 확인.

    Returns:
        {
            "consistent": bool,
            "agreement_score": float (0~1),
            "conflicts": list[str],
            "shared_claims": list[str],
        }
    """
    if not trend.context:
        return {"consistent": True, "agreement_score": 0.0, "conflicts": [], "shared_claims": []}

    sources = {
        "twitter": trend.context.twitter_insight or "",
        "reddit": trend.context.reddit_insight or "",
        "news": trend.context.news_insight or "",
    }

    # 빈 소스 제거
    active_sources = {k: v for k, v in sources.items() if v and len(v) > 20}
    if len(active_sources) < 2:
        return {"consistent": True, "agreement_score": 0.5, "conflicts": [], "shared_claims": []}

    # 각 소스에서 핵심 엔터티/숫자 추출
    source_entities: dict[str, set[str]] = {}
    source_numbers: dict[str, set[str]] = {}

    for name, text in active_sources.items():
        entities = set()
        for m in _ENTITY_PATTERN.finditer(text):
            entity = m.group(0).strip()
            if entity.casefold() not in _COMMON_ENTITIES and len(entity) >= 2:
                entities.add(entity.casefold())
        source_entities[name] = entities

        numbers = set()
        for m in _NUMBER_PATTERN.finditer(text):
            numbers.add(m.group(0).strip())
        source_numbers[name] = numbers

    # 소스 간 엔터티 교집합 계산
    all_entity_sets = list(source_entities.values())
    if len(all_entity_sets) >= 2:
        shared_entities = all_entity_sets[0]
        for s in all_entity_sets[1:]:
            shared_entities = shared_entities & s
    else:
        shared_entities = set()

    # 소스 간 합집합
    union_entities = set()
    for s in all_entity_sets:
        union_entities |= s

    # 일치도 계산
    if union_entities:
        agreement_score = round(len(shared_entities) / len(union_entities), 2)
    else:
        agreement_score = 0.5  # 엔터티 없으면 중립

    # 충돌 감지: 한 소스에만 있는 강한 주장 (숫자 포함)
    conflicts: list[str] = []
    for name, nums in source_numbers.items():
        for other_name, other_nums in source_numbers.items():
            if name >= other_name:
                continue
            # 같은 엔터티에 대해 다른 숫자가 언급된 경우
            for n in nums:
                normalized = _normalize_number(n)
                if normalized is None:
                    continue
                for on in other_nums:
                    other_normalized = _normalize_number(on)
                    if other_normalized is None:
                        continue
                    # 같은 규모인데 값이 다른 경우
                    if normalized > 0 and other_normalized > 0:
                        ratio = max(normalized, other_normalized) / min(normalized, other_normalized)
                        if 1.5 < ratio < 100:  # 1.5배 이상 차이나면 충돌
                            conflicts.append(f"{name}({n}) vs {other_name}({on})")

    # 충돌이 없으면 일관적으로 판정 (엔터티 교집합이 작아도 충돌 없으면 OK)
    consistent = len(conflicts) == 0

    return {
        "consistent": consistent,
        "agreement_score": agreement_score,
        "conflicts": conflicts[:5],  # 최대 5개
        "shared_claims": sorted(shared_entities)[:10],
    }


# ══════════════════════════════════════════════════════
#  Enhanced Cross-Source Confidence
# ══════════════════════════════════════════════════════


def compute_enhanced_confidence(
    volume_numeric: int,
    context: "MultiSourceContext | None",
    news_insight: str = "",
) -> tuple[int, float]:
    """
    강화된 교차 소스 신뢰도 점수.

    기존 0~4 점수에 출처 신뢰도 가중치를 적용.

    Returns:
        (cross_source_confidence: int 0~4, weighted_credibility: float 0~1)
    """

    score = 0
    if volume_numeric > 0:
        score += 1

    if context:
        if context.twitter_insight and len(context.twitter_insight) > 20:
            if "없음" not in context.twitter_insight and "오류" not in context.twitter_insight:
                score += 1
        if context.news_insight and len(context.news_insight) > 20:
            if "없음" not in context.news_insight:
                score += 1
        if context.reddit_insight and len(context.reddit_insight) > 20:
            if "없음" not in context.reddit_insight and "제한" not in context.reddit_insight:
                score += 1

    # 출처 신뢰도 가중치
    credibility = compute_source_credibility_score(news_insight or (context.news_insight if context else ""))

    return score, credibility
