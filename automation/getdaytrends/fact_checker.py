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
    from .models import MultiSourceContext, ScoredTrend, TweetBatch
except ImportError:
    from models import MultiSourceContext, ScoredTrend, TweetBatch

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
            f"실패 (정확도={self.accuracy_score:.0%}, 미검증={self.unverified_claims}, 환각={self.hallucinated_claims})"
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
_COMPARISON_PATTERN = re.compile(
    r"(\S+)\s*(?:보다|대비|비해|대신|반면|달리|than|versus|vs\.?)\s+(\S+)"
    r"|(\S+)\s*(?:대|vs\.?)\s*(\S+)"
    r"|(\S+)\s*(?:보다|대비|비해)\s*(\d+(?:\.\d+)?)\s*배",
    re.IGNORECASE,
)
_COMPARISON_SPLIT_RE = re.compile(
    r"\s*(?:보다|대비|비해|대신|반면|달리|than|versus|vs\.?|대)\s*",
    re.IGNORECASE,
)

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


def _claim_sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"[.!?\n]+", text) if len(sentence.strip()) >= 5]


def _add_claim(
    claims: list[Claim],
    seen_values: set[str],
    claim_type: ClaimType,
    value: str,
    context: str,
    *,
    min_len: int = 1,
) -> None:
    value = value.strip()
    if not value or len(value) < min_len or value in seen_values:
        return
    seen_values.add(value)
    claims.append(Claim(claim_type=claim_type, value=value, context=context))


def _extract_number_claims(sentence: str, claims: list[Claim], seen_values: set[str]) -> None:
    for match in _NUMBER_PATTERN.finditer(sentence):
        _add_claim(claims, seen_values, ClaimType.NUMBER, match.group(0), sentence)


def _extract_percentage_claims(sentence: str, claims: list[Claim], seen_values: set[str]) -> None:
    for match in re.finditer(r"[+-]?\d+(?:\.\d+)?%", sentence):
        _add_claim(claims, seen_values, ClaimType.PERCENTAGE, match.group(0), sentence)


def _extract_date_claims(sentence: str, claims: list[Claim], seen_values: set[str]) -> None:
    for match in _DATE_PATTERN.finditer(sentence):
        _add_claim(claims, seen_values, ClaimType.DATE, match.group(0), sentence)


def _extract_quote_claims(sentence: str, claims: list[Claim], seen_values: set[str]) -> None:
    for match in _QUOTE_PATTERN.finditer(sentence):
        _add_claim(claims, seen_values, ClaimType.QUOTE, match.group(1) or match.group(2) or "", sentence, min_len=6)


def _extract_entity_claims(sentence: str, claims: list[Claim], seen_values: set[str]) -> None:
    for match in _ENTITY_PATTERN.finditer(sentence):
        value = match.group(0).strip()
        if value.casefold() in _COMMON_ENTITIES:
            continue
        _add_claim(claims, seen_values, ClaimType.ENTITY, value, sentence, min_len=2)


def _extract_comparison_claims(sentence: str, claims: list[Claim], seen_values: set[str]) -> None:
    for match in _COMPARISON_PATTERN.finditer(sentence):
        _add_claim(claims, seen_values, ClaimType.COMPARISON, match.group(0), sentence, min_len=6)


def extract_claims(text: str) -> list[Claim]:
    """Extract verifiable claims from generated content."""
    if not text:
        return []

    claims: list[Claim] = []
    seen_values: set[str] = set()
    extractors = (
        _extract_number_claims,
        _extract_percentage_claims,
        _extract_date_claims,
        _extract_quote_claims,
        _extract_entity_claims,
        _extract_comparison_claims,
    )
    for sentence in _claim_sentences(text):
        for extractor in extractors:
            extractor(sentence, claims, seen_values)
    return claims

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


def _mark_verified(claim: Claim, confidence: float, source_match: str = "") -> None:
    claim.verified = True
    claim.confidence = confidence
    if source_match:
        claim.source_match = source_match


def _verify_number_claim(claim: Claim, source_corpus: str) -> None:
    if claim.value in source_corpus:
        _mark_verified(claim, 1.0, _find_context_around(source_corpus, claim.value))
        return

    num = re.search(r"\d+(?:[,.]?\d+)*", claim.value)
    if num and num.group(0) in source_corpus:
        _mark_verified(claim, 0.8, _find_context_around(source_corpus, num.group(0)))
        return

    claim_num = _normalize_number(claim.value)
    if claim_num is None:
        return

    for match in _NUMBER_PATTERN.finditer(source_corpus):
        source_num = _normalize_number(match.group(0))
        if source_num is not None and source_num > 0:
            ratio = claim_num / source_num
            if 0.8 <= ratio <= 1.2:
                _mark_verified(claim, 0.6, match.group(0))
                break


def _verify_percentage_claim(claim: Claim, source_corpus: str) -> None:
    if claim.value in source_corpus:
        _mark_verified(claim, 1.0, _find_context_around(source_corpus, claim.value))
        return

    pct_num = re.search(r"(\d+(?:\.\d+)?)", claim.value)
    if not pct_num:
        return

    for match in re.finditer(r"(\d+(?:\.\d+)?)%", source_corpus):
        if pct_num.group(1) == match.group(1):
            _mark_verified(claim, 0.9, match.group(0))
            break


def _verify_date_claim(claim: Claim, source_corpus: str, source_lower: str, value_lower: str) -> None:
    if value_lower in source_lower:
        _mark_verified(claim, 1.0, _find_context_around(source_corpus, claim.value))
        return

    date_nums = re.findall(r"\d+", claim.value)
    if date_nums and any(n in source_corpus for n in date_nums if len(n) >= 2):
        _mark_verified(claim, 0.5)


def _verify_entity_claim(claim: Claim, source_corpus: str, source_lower: str, value_lower: str) -> None:
    if value_lower in source_lower:
        _mark_verified(claim, 1.0, _find_context_around(source_corpus, claim.value))
        return

    if len(claim.value) < 3:
        return

    for segment_len in range(len(claim.value), max(2, len(claim.value) // 2 - 1), -1):
        segment = claim.value[:segment_len]
        if segment.lower() in source_lower:
            _mark_verified(claim, 0.5, segment)
            break


def _verify_quote_claim(claim: Claim, source_corpus: str, source_lower: str, value_lower: str) -> None:
    if value_lower in source_lower:
        _mark_verified(claim, 1.0, _find_context_around(source_corpus, claim.value))
        return

    words = [w for w in claim.value.split() if len(w) >= 2]
    if words:
        matched = sum(1 for w in words if w.lower() in source_lower)
        if matched / len(words) >= 0.7:
            _mark_verified(claim, 0.4, "(?듭떖 ?⑥뼱 遺遺?留ㅼ묶)")


def _verify_comparison_claim(claim: Claim, source_corpus: str, source_lower: str, value_lower: str) -> None:
    if value_lower in source_lower:
        _mark_verified(claim, 1.0, _find_context_around(source_corpus, claim.value))
        return

    parts = _COMPARISON_SPLIT_RE.split(claim.value)
    if len(parts) >= 2:
        matched = sum(1 for p in parts if p.strip().lower() in source_lower)
        if matched >= 1:
            _mark_verified(claim, 0.5)
    return

    if value_lower in source_lower:
        _mark_verified(claim, 1.0, _find_context_around(source_corpus, claim.value))
        return

    parts = re.split(r"蹂대떎|?鍮?鍮꾪빐|諛섎㈃", claim.value)
    if len(parts) >= 2:
        matched = sum(1 for p in parts if p.strip().lower() in source_lower)
        if matched >= 1:
            _mark_verified(claim, 0.5)


def verify_claim_against_source(claim: Claim, source_corpus: str) -> Claim:
    """Verify a single claim against the source corpus and mutate the claim."""
    if not source_corpus:
        claim.confidence = 0.0
        return claim

    source_lower = source_corpus.lower()
    value_lower = claim.value.lower()

    if claim.claim_type == ClaimType.NUMBER:
        _verify_number_claim(claim, source_corpus)
    elif claim.claim_type == ClaimType.PERCENTAGE:
        _verify_percentage_claim(claim, source_corpus)
    elif claim.claim_type == ClaimType.DATE:
        _verify_date_claim(claim, source_corpus, source_lower, value_lower)
    elif claim.claim_type == ClaimType.ENTITY:
        _verify_entity_claim(claim, source_corpus, source_lower, value_lower)
    elif claim.claim_type == ClaimType.QUOTE:
        _verify_quote_claim(claim, source_corpus, source_lower, value_lower)
    elif claim.claim_type == ClaimType.COMPARISON:
        _verify_comparison_claim(claim, source_corpus, source_lower, value_lower)

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


def _source_credibility_for_trend(trend: ScoredTrend) -> float:
    news_insight = ""
    if trend.context and trend.context.news_insight:
        news_insight = trend.context.news_insight
    return compute_source_credibility_score(news_insight)


def _classify_verified_claims(
    claims: list[Claim],
    source_corpus: str,
    *,
    strict_mode: bool,
) -> tuple[int, int, int, list[str]]:
    verified = 0
    hallucinated = 0
    unverified = 0
    issues: list[str] = []

    for claim in claims:
        verify_claim_against_source(claim, source_corpus)
        if claim.verified:
            verified += 1
        elif claim.claim_type in (ClaimType.QUOTE, ClaimType.ENTITY):
            hallucinated += 1
            issues.append(f"[?섍컖 ?섏떖] {claim.claim_type.value}: '{claim.value}' - ?뚯뒪?먯꽌 ?뺤씤 遺덇?")
        elif claim.claim_type == ClaimType.NUMBER and not strict_mode:
            unverified += 1
            issues.append(f"[誘멸?利??섏튂] '{claim.value}' - ?뚯뒪?먯꽌 吏곸젒 ?뺤씤 遺덇?")
        else:
            unverified += 1

    return verified, hallucinated, unverified, issues


def _apply_claim_counts(
    result: FactCheckResult,
    claims: list[Claim],
    counts: tuple[int, int, int, list[str]],
) -> None:
    verified, hallucinated, unverified, issues = counts
    result.claims = claims
    result.verified_claims = verified
    result.hallucinated_claims = hallucinated
    result.unverified_claims = unverified
    result.issues.extend(issues)
    result.accuracy_score = round(verified / result.total_claims, 2) if result.total_claims > 0 else 1.0


def _apply_deepeval_check(result: FactCheckResult, text: str, trend: ScoredTrend) -> None:
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
            if eval_result.hallucination_score > 0.7:
                result.passed = False
                log.warning(f"[DeepEval] '{trend.keyword}' ?섍컖 ?먯닔 ?믪쓬: {eval_result.hallucination_score:.2f}")
    except ImportError:
        pass
    except Exception as e:
        log.debug(f"[DeepEval] 蹂댁“ ?됯? ?ㅽ궢: {e}")


def verify_content(
    text: str,
    trend: ScoredTrend,
    *,
    strict_mode: bool = False,
    min_accuracy: float = 0.6,
) -> FactCheckResult:
    """Verify generated content against the source data carried by a scored trend."""
    result = FactCheckResult()
    if not text or not text.strip():
        result.passed = True
        return result

    claims = extract_claims(text)
    result.total_claims = len(claims)
    if not claims:
        result.passed = True
        result.accuracy_score = 1.0
        return result

    source_corpus = _build_source_corpus(trend)
    result.source_credibility = _source_credibility_for_trend(trend)
    _apply_claim_counts(
        result,
        claims,
        _classify_verified_claims(claims, source_corpus, strict_mode=strict_mode),
    )
    result.passed = result.hallucinated_claims == 0 and result.accuracy_score >= min_accuracy
    _apply_deepeval_check(result, text, trend)
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


def _consistency_result(
    consistent: bool,
    agreement_score: float,
    conflicts: list[str] | None = None,
    shared_claims: list[str] | None = None,
) -> dict:
    return {
        "consistent": consistent,
        "agreement_score": agreement_score,
        "conflicts": conflicts or [],
        "shared_claims": shared_claims or [],
    }


def _active_consistency_sources(trend: ScoredTrend) -> dict[str, str]:
    if not trend.context:
        return {}

    sources = {
        "twitter": trend.context.twitter_insight or "",
        "reddit": trend.context.reddit_insight or "",
        "news": trend.context.news_insight or "",
    }
    return {name: text for name, text in sources.items() if text and len(text) > 20}


def _extract_consistency_terms(active_sources: dict[str, str]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    source_entities: dict[str, set[str]] = {}
    source_numbers: dict[str, set[str]] = {}

    for name, text in active_sources.items():
        source_entities[name] = {
            entity.casefold()
            for match in _ENTITY_PATTERN.finditer(text)
            if (entity := match.group(0).strip()).casefold() not in _COMMON_ENTITIES and len(entity) >= 2
        }
        source_numbers[name] = {match.group(0).strip() for match in _NUMBER_PATTERN.finditer(text)}

    return source_entities, source_numbers


def _shared_and_union_entities(source_entities: dict[str, set[str]]) -> tuple[set[str], set[str]]:
    entity_sets = list(source_entities.values())
    if not entity_sets:
        return set(), set()

    shared_entities = set.intersection(*entity_sets) if len(entity_sets) >= 2 else set()
    union_entities = set.union(*entity_sets)
    return shared_entities, union_entities


def _entity_agreement_score(shared_entities: set[str], union_entities: set[str]) -> float:
    if not union_entities:
        return 0.5
    return round(len(shared_entities) / len(union_entities), 2)


def _normalized_numbers(numbers: set[str]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for number in numbers:
        value = _normalize_number(number)
        if value is not None and value > 0:
            normalized[number] = value
    return normalized


def _number_conflicts(source_numbers: dict[str, set[str]]) -> list[str]:
    conflicts: list[str] = []
    normalized_by_source = {name: _normalized_numbers(numbers) for name, numbers in source_numbers.items()}
    source_names = sorted(normalized_by_source)

    for index, name in enumerate(source_names):
        for other_name in source_names[index + 1 :]:
            for number, value in normalized_by_source[name].items():
                for other_number, other_value in normalized_by_source[other_name].items():
                    ratio = max(value, other_value) / min(value, other_value)
                    if 1.5 < ratio < 100:
                        conflicts.append(f"{name}({number}) vs {other_name}({other_number})")

    return conflicts


def check_cross_source_consistency(trend: ScoredTrend) -> dict:
    """
    Validate that core claims agree across Twitter, Reddit, and News context.

    Returns:
        {
            "consistent": bool,
            "agreement_score": float (0~1),
            "conflicts": list[str],
            "shared_claims": list[str],
        }
    """
    active_sources = _active_consistency_sources(trend)
    if not trend.context:
        return _consistency_result(True, 0.0)
    if len(active_sources) < 2:
        return _consistency_result(True, 0.5)

    source_entities, source_numbers = _extract_consistency_terms(active_sources)
    shared_entities, union_entities = _shared_and_union_entities(source_entities)
    conflicts = _number_conflicts(source_numbers)

    return _consistency_result(
        len(conflicts) == 0,
        _entity_agreement_score(shared_entities, union_entities),
        conflicts[:5],
        sorted(shared_entities)[:10],
    )

def compute_enhanced_confidence(
    volume_numeric: int,
    context: "MultiSourceContext | None",
    news_insight: str = "",
) -> tuple[int, float]:
    """
    Compute cross-source confidence and weighted source credibility.

    Returns:
        (cross_source_confidence: int 0~4, weighted_credibility: float 0~1)
    """
    score = int(volume_numeric > 0) + _context_confidence_signal_count(context)
    credibility = compute_source_credibility_score(news_insight or (context.news_insight if context else ""))
    return score, credibility


def _context_confidence_signal_count(context: "MultiSourceContext | None") -> int:
    if not context:
        return 0
    return sum(
        (
            _usable_context_signal(context.twitter_insight, ("?놁쓬", "?ㅻ쪟")),
            _usable_context_signal(context.news_insight, ("?놁쓬",)),
            _usable_context_signal(context.reddit_insight, ("?놁쓬", "?쒗븳")),
        )
    )


def _usable_context_signal(value: str, blocked_markers: tuple[str, ...]) -> bool:
    return bool(value and len(value) > 20 and not any(marker in value for marker in blocked_markers))
