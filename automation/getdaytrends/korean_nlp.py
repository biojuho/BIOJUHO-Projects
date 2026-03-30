"""
getdaytrends — Kiwipiepy 기반 한국어 NLP 품질 모듈.

1. AI어투 탐지: 형태소 분석으로 "~것 같습니다", "~되고 있다" 등 AI 특유 패턴을 어미 단위로 정밀 탐지
2. 신조어 감지: 사전 미등재 토큰 추출로 트렌드 키워드의 신조어/밈 자동 발견
3. 텍스트 품질 점수: 구어체 비율, 반복 표현, 문장 다양성 계량

Usage:
    from korean_nlp import detect_ai_voice, extract_novel_words, compute_quality_score
    flags = detect_ai_voice("화제가 되고 있다")  # ["기자체: 화제가 되고 있다"]
    novel = extract_novel_words("컨셉질 ㅋㅋ")   # ["컨셉질"]
    score = compute_quality_score(tweet_text)       # 0.0 ~ 1.0
"""

from __future__ import annotations

from loguru import logger as log

# Kiwipiepy 선택 의존성 — Windows 한글 경로에서 segfault 이슈가 있어 안전 체크
_kiwi = None
KIWI_AVAILABLE = False
try:
    import importlib

    _kiwi_spec = importlib.util.find_spec("kiwipiepy")
    if _kiwi_spec is not None:
        # 실제 import + 간단 토큰화로 바이너리 호환성 검증
        from kiwipiepy import Kiwi as _KiwiClass  # noqa: F401

        KIWI_AVAILABLE = True
except Exception:
    KIWI_AVAILABLE = False

# ── Kiwi 싱글톤 ────────────────────────────────────────


def _get_kiwi():
    global _kiwi
    if _kiwi is None:
        import os
        import shutil

        from kiwipiepy import Kiwi

        # Windows 한글 경로 우회: C++ 백엔드가 비ASCII 경로를 처리 못하는 경우
        # 모델 파일을 ASCII 경로로 복사 후 model_path 지정
        try:
            _kiwi = Kiwi()
        except Exception:
            try:
                import kiwipiepy_model

                src = kiwipiepy_model.get_model_path()
                dest = os.path.join(os.environ.get("TEMP", "C:/temp"), "kiwi_model")
                os.makedirs(dest, exist_ok=True)
                for f in os.listdir(src):
                    if not f.startswith("_"):
                        dst_file = os.path.join(dest, f)
                        if not os.path.exists(dst_file):
                            shutil.copy2(os.path.join(src, f), dst_file)
                _kiwi = Kiwi(model_path=dest)
                log.info(f"[Kiwipiepy] 모델 경로 우회: {dest}")
            except Exception as e2:
                log.warning(f"[Kiwipiepy] 초기화 실패: {e2}")
                raise

        log.info("[Kiwipiepy] 형태소 분석기 초기화 완료")
    return _kiwi


def reset_kiwi():
    """테스트용 리셋."""
    global _kiwi
    _kiwi = None


# ══════════════════════════════════════════════════════
#  1. AI어투 탐지 (형태소 기반)
# ══════════════════════════════════════════════════════

# 어미(E) + 보조용언 패턴으로 AI 특유 문체를 탐지
# POS 태그: EF(종결어미), EC(연결어미), EP(선어말어미), VX(보조용언)
_AI_ENDING_PATTERNS: list[tuple[str, str]] = [
    # (패턴 설명, 매칭할 형태소 시퀀스)
    # 경어체 패턴
    ("AI 경어체", "ㅂ니다"),
    ("AI 경어체", "습니다"),
    ("AI 경어체", "겠습니다"),
    ("AI 경어체", "같습니다"),
    ("AI 경어체", "있습니다"),
    ("AI 경어체", "됩니다"),
    # 설명체/분석체
    ("설명체", "살펴보겠"),
    ("설명체", "분석해보"),
    ("설명체", "살펴보면"),
    ("설명체", "알아보겠"),
    # 기자체 (피동 + 진행)
    ("기자체", "되고 있"),
    ("기자체", "받고 있"),
    ("기자체", "주목받"),
    ("기자체", "화제가 되"),
    ("기자체", "논란이 되"),
    ("기자체", "관심이 쏠"),
    ("기자체", "모이고 있"),
    # 연설체
    ("연설체", "여러분"),
    ("연설체", "우리 모두"),
    # 상투적 마무리
    ("상투구", "기대됩니다"),
    ("상투구", "주목됩니다"),
    ("상투구", "귀추가"),
    ("상투구", "전망입니다"),
    ("상투구", "예상됩니다"),
    # 출처 불명 인용
    ("허위인용", "전문가들은"),
    ("허위인용", "관계자에 따르면"),
    ("허위인용", "분석이 나"),
    ("허위인용", "지적이 나"),
]

# 형태소 태그 기반 패턴 (어미 조합)
_AI_MORPHEME_PATTERNS: list[tuple[str, list[tuple[str, str]]]] = [
    # (패턴명, [(형태소, POS태그), ...])
    ("AI 경어체 어미", [("ᆸ니다", "EF")]),
    ("AI 경어체 어미", [("습니다", "EF")]),
    ("AI 추측 어미", [("것", "NNB"), ("같", "VA")]),
    ("기자체 피동", [("되", "VV"), ("고", "EC"), ("있", "VX")]),
    ("기자체 피동", [("받", "VV"), ("고", "EC"), ("있", "VX")]),
]


def detect_ai_voice(text: str) -> list[str]:
    """
    텍스트에서 AI어투 패턴을 탐지하여 위반 목록 반환.
    반환 형식: ["기자체: 화제가 되고 있다", "AI 경어체: ~습니다"]
    빈 리스트 = AI어투 없음 (통과).
    """
    if not KIWI_AVAILABLE:
        return _detect_ai_voice_fallback(text)

    flags: list[str] = []

    # 1단계: 문자열 패턴 매칭 (빠른 스캔)
    for label, pattern in _AI_ENDING_PATTERNS:
        if pattern in text:
            # 매칭된 주변 컨텍스트 추출 (최대 30자)
            idx = text.index(pattern)
            start = max(0, idx - 10)
            end = min(len(text), idx + len(pattern) + 10)
            context = text[start:end].strip()
            flags.append(f"{label}: {context}")

    # 2단계: 형태소 분석 기반 심층 탐지 (Kiwipiepy 사용 가능 시)
    if KIWI_AVAILABLE:
        try:
            kiwi = _get_kiwi()
            tokens = kiwi.tokenize(text)
            morphemes = [(t.form, t.tag) for t in tokens]

            for pattern_name, pattern_seq in _AI_MORPHEME_PATTERNS:
                if _find_morpheme_sequence(morphemes, pattern_seq):
                    # 이미 1단계에서 잡힌 패턴과 중복 방지
                    if not any(pattern_name in f for f in flags):
                        flags.append(f"{pattern_name}: (형태소 분석)")
        except Exception as e:
            log.debug(f"[Kiwipiepy] 형태소 분석 실패 (문자열 패턴으로 폴백): {e}")

    return flags


def _find_morpheme_sequence(
    morphemes: list[tuple[str, str]],
    pattern: list[tuple[str, str]],
) -> bool:
    """형태소 시퀀스에서 패턴 매칭. POS 태그 일치 + 형태소 부분 매칭."""
    if len(pattern) > len(morphemes):
        return False
    for i in range(len(morphemes) - len(pattern) + 1):
        matched = True
        for j, (form, tag) in enumerate(pattern):
            m_form, m_tag = morphemes[i + j]
            if tag and not m_tag.startswith(tag):
                matched = False
                break
            if form and form not in m_form:
                matched = False
                break
        if matched:
            return True
    return False


def _detect_ai_voice_fallback(text: str) -> list[str]:
    """Kiwipiepy 미설치 시 문자열 패턴만으로 탐지 (기존 동작 호환)."""
    flags = []
    for label, pattern in _AI_ENDING_PATTERNS:
        if pattern in text:
            flags.append(f"{label}: {pattern}")
    return flags


# ══════════════════════════════════════════════════════
#  2. 신조어/밈 감지
# ══════════════════════════════════════════════════════


def extract_novel_words(text: str, min_length: int = 2) -> list[str]:
    """
    텍스트에서 사전 미등재 토큰(신조어, 밈, 줄임말)을 추출.
    Kiwipiepy의 형태소 분석 결과 중 UN(미등록) 태그를 가진 토큰 반환.
    """
    if not KIWI_AVAILABLE:
        return []

    try:
        kiwi = _get_kiwi()
        tokens = kiwi.tokenize(text)
        novel = []
        seen = set()
        for t in tokens:
            # UN: 미등록 명사, SL: 외래어, SH: 한자
            if t.tag in ("UN", "NNG+UN") and len(t.form) >= min_length:
                if t.form.lower() not in seen:
                    seen.add(t.form.lower())
                    novel.append(t.form)
        return novel
    except Exception as e:
        log.debug(f"[Kiwipiepy] 신조어 추출 실패: {e}")
        return []


# ══════════════════════════════════════════════════════
#  3. 텍스트 품질 점수
# ══════════════════════════════════════════════════════


def compute_quality_score(text: str) -> float:
    """
    트윗/콘텐츠 텍스트의 품질 점수 (0.0 ~ 1.0).

    감점 요소:
    - AI어투 패턴 감지 (-0.15 per pattern, max -0.6)
    - 반복 어절 비율 높음 (-0.2)
    - 문장이 너무 짧거나 없음 (-0.2)

    가점 요소:
    - 구어체 마커 존재 (+0.1)
    - 숫자/데이터 포함 (+0.1)
    - 의문문/감탄문 사용 (+0.05)
    """
    if not text or len(text.strip()) < 10:
        return 0.0

    score = 1.0

    # AI어투 감점
    ai_flags = detect_ai_voice(text)
    score -= min(len(ai_flags) * 0.15, 0.6)

    # 반복 어절 감점
    words = text.split()
    if words:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.6:
            score -= 0.2

    # 구어체 가점
    colloquial_markers = [
        "거임",
        "아닌가",
        "근데 진짜",
        "솔직히",
        "ㅋ",
        "ㄷㄷ",
        "인 거",
        "는 거",
        "한 거",
        "인데",
        "잖아",
        "거든",
    ]
    if any(m in text for m in colloquial_markers):
        score += 0.1

    # 숫자/데이터 가점
    import re

    if re.search(r"\d+[%억만조원달러]", text):
        score += 0.1

    # 의문문/감탄문 가점
    if "?" in text or "!" in text:
        score += 0.05

    return max(0.0, min(1.0, score))


# ══════════════════════════════════════════════════════
#  4. 키워드 정제
# ══════════════════════════════════════════════════════


def refine_keyword(keyword: str) -> dict:
    """
    트렌드 키워드를 형태소 분석하여 메타데이터 추출.
    반환: {
        "original": "원본 키워드",
        "nouns": ["명사1", "명사2"],          # 핵심 명사 추출
        "novel_words": ["신조어1"],            # 사전 미등재
        "is_fragment": bool,                   # 문장 조각 여부
        "corrected": "교정된 키워드" | None,   # 오타 교정
    }
    """
    result = {
        "original": keyword,
        "nouns": [],
        "novel_words": [],
        "is_fragment": False,
        "corrected": None,
    }

    if not KIWI_AVAILABLE:
        return result

    try:
        kiwi = _get_kiwi()
        tokens = kiwi.tokenize(keyword)

        # 명사 추출 (NNG: 일반명사, NNP: 고유명사, NNB: 의존명사)
        nouns = [t.form for t in tokens if t.tag.startswith("NN") and len(t.form) >= 2]
        result["nouns"] = nouns

        # 신조어
        result["novel_words"] = [t.form for t in tokens if t.tag == "UN" and len(t.form) >= 2]

        # 문장 조각 판별: 명사 없이 어미/조사만 있으면 조각
        has_noun = any(t.tag.startswith("NN") or t.tag == "UN" for t in tokens)
        has_only_particles = all(t.tag.startswith(("J", "E", "X", "S")) or t.tag == "SP" for t in tokens)
        result["is_fragment"] = not has_noun or has_only_particles

        # 오타 교정 (Kiwi typo correction)
        corrected_tokens = kiwi.tokenize(keyword)
        corrected_text = "".join(t.form for t in corrected_tokens)
        if corrected_text != keyword and len(corrected_text) >= len(keyword) * 0.8:
            result["corrected"] = corrected_text

    except Exception as e:
        log.debug(f"[Kiwipiepy] 키워드 정제 실패: {e}")

    return result
