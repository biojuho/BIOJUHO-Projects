"""훅 커널 소재 판별을 레이더 항목에 얹는다.

레이더의 X 적합도 점수와 커널의 소재 판별은 **서로 다른 축**이다.

- 적합도 점수 : 지금 퍼지고 있는가 (분당 조회·경과 시간·교차 확산)
- 커널 판별   : X에서 판정이 붙는가 (가해자 명확성·낙차·검증 필요성)

점수 순으로 위에서부터 집으면 커널 기준으로는 잘못 고르게 된다. 2026-08-06 관측에서
적합도 96점이던 "연봉 1억 주면 가능?"은 쌍방 논쟁형이라 커널로는 죽는 축이었고,
78점 "위고비·마운자로 오남용 우려 의약품 지정"은 검증이 먼저인 소재였다.

**한계를 먼저 밝힌다.** 이 판정은 제목 한 줄만 보는 휴리스틱이다. 가해자가 정말
일방적인지, 낙차가 실제로 있는지는 원문을 열어야 확정된다. 그래서 결과에 판정과 함께
**그렇게 본 근거(signals)**를 실어 보낸다 — 사람이 뒤집을 수 있어야 쓸모가 있다.

커널 원문: ~/Desktop/보류/X/reference/hook-kernel-v1.4.md (5-1절 소재 판별, 2-1절 검증 트리거)
"""

from __future__ import annotations

import re
from typing import Any

# ── 5-1절 사는 축① : 가해자가 명확한 일방 부당함 ─────────────────────────
# 역할명이 있어야 "누가 그랬는지"가 0초에 잡힌다. 이름 없는 "어떤 사람"은 힘이 없다.
_ACTOR_TERMS = (
    "남편", "아내", "시어머니", "시아버지", "시댁", "친정", "장모", "장인", "며느리", "사위",
    "팀장", "부장", "과장", "사장", "상사", "선배", "후배", "동료", "직원", "알바",
    "손님", "고객", "진상", "이웃", "윗집", "아랫집", "집주인", "세입자",
    "기사", "택배", "점주", "원장", "교수", "담임", "학부모", "친구", "지인",
    "남친", "여친", "전남친", "전여친", "엄마", "아빠", "부모", "오빠", "누나", "형", "동생",
    "와이프", "유부남", "유부녀",
)

_WRONGDOING_TERMS = (
    "갑질", "떠넘", "뺏", "강요", "무시", "방치", "폭언", "욕설", "협박", "바가지",
    "몰래", "무단", "속이", "속였", "거짓말", "잠수", "먹튀", "안 준", "안 줬", "안줌",
    "밀린", "체불", "미지급", "손절", "차별", "부당", "억지", "진상짓", "새치기",
    "떼먹", "떼어먹", "안 갚", "안갚", "미납", "가로채", "빼돌", "외도", "바람핀", "바람피운",
)

# ── 5-1절 사는 축② : 가해자 없는 강한 낙차 ────────────────────────────────
_GAP_TERMS = (
    "알고 보니", "알고보니", "반전", "뜻밖", "사실은", "정체", "결말",
    "충격", "소름", "레전드", "기적", "실화", "이럴 수가", "예상 밖", "예상밖",
    # 역접이 곧 낙차다. 2026-08-06에 "장사가 너무 잘돼서, 오히려 망했다"(노출 3위)를
    # 낙차 없음으로 오판해 추가했다.
    "오히려", "도리어", "인데도", "줄 알았는데", "줄알았는데", "그런데 정작", "했는데 정작",
    "안 했는데", "했더니", "하자마자",
)

# 0011: "이유"·"근황"은 단독이면낙차가 아니다 — 설명글이나 근황 보고가 사는 축 64%를 만든다.
# 강한 신호가 없을 때 이 두 어휘만 있으면 unknown으로 내려 원문을 열게 한다.
# 단, 구체적 개체가 예기치 않은 행동을 했을 때의 "이유"는 서사 구조로 포착한다.
_WEAK_GAP_TERMS = ("이유", "근황")

# 커널 1-3절이 정의한 낙차 4종을 구조로 잡는다. 어휘가 없어도 두 요소가 부딪히면 낙차다.
# 처음에는 ①만 구현해서 "오만석 A+ 안 준다"(노출 4위) "JYP 도시락 공짜"(5위)를 놓쳤다.
_GAP_PATTERNS = (
    # ① 예상-결과 역전
    (re.compile(r"(?:잘|많이|열심히|성공|대박|1위).{0,18}(?:망|실패|손해|잃|끝났|무너)"), "예상-결과 역전"),
    (re.compile(r"(?:공짜|무료|선물|호의).{0,18}(?:청구|요구|돈|받아)"), "예상-결과 역전"),
    # ② 규칙-행동 역전 — 원칙을 세워두고 스스로 깨거나, 예외 없이 지키는 쪽 모두 낙차다
    (re.compile(r"(?:절대|무조건|한 번도|한번도|평생)\s*(?:안|못|없)"), "규칙-행동 역전"),
    (re.compile(r"(?:규정|원칙|금지|만점|100점).{0,20}(?:없|안|예외|깨|어긴)"), "규칙-행동 역전"),
    # ③ 규모-생활 격차 — 큰 단위가 사소한 생활 소재와 붙을 때
    (re.compile(r"\d+\s*(?:억|천만|백만)\D{0,20}(?:라면|커피|도시락|택시|치킨|김밥|편의점|월세|용돈)"), "규모-생활 격차"),
    (re.compile(r"(?:도시락|간식|커피|물|화장지).{0,14}(?:공짜|무료|무제한|다 주|퍼줌|퍼준)"), "규모-생활 격차"),
    # ④ 관계-의미 역전 — 가까운 관계에서 예상과 반대 행동이 나올 때
    (re.compile(r"(?:엄마|아빠|아들|딸|남편|아내|사장|팀장|선생|담임).{0,16}(?:뜻밖|의외|반대로|처음으로|몰래)"), "관계-의미 역전"),
    # ⑤ 대상 전환 — 감정·행위의 대상이 도중에 바뀔 때 (0005 구조 패턴)
    (re.compile(r"\S+에게.{2,30}\S+에게"), "대상 전환"),
    # ⑥ 서사 이유 — 구체적 개체가 예기치 않은 행동을 했을 때의 "이유" (0011)
    # "식당이 휴가를 간 이유"는 낙차, "옷차림이 중요해지는 이유"는 설명글.
    # 추상 동사(중요해지다, 늘다, 줄다 등)는 제외해서 설명글을 걸러낸다.
    (re.compile(r"(?:식당|가게|회사|카페|편의점|병원|학교|스타벅스|맥도날드).{2,25}(?:간|접은|닫은|그둔|바뀐)\s*이유"), "서사 이유"),
)

# ── 5-1절 죽는 축① : 쌍방 논쟁형 (독자 판단이 갈림) ───────────────────────
_DEBATE_TERMS = (
    "논란", "갑론을박", "찬반", "반반", "갈린", "갈림", "어디까지", "예민한", "제가 이상한",
    "누가 잘못", "누구 잘못", "vs", "VS",
)
_DEBATE_PATTERNS = (
    re.compile(r"(?:가능|맞나요|맞나|아닌가요|아님\?|어때요|어떻게 생각)\s*[?？]?\s*$"),
    re.compile(r"(?:뭡니까|인가요|일까요)\s*[?？]{1,3}\s*$"),
)

# ── 2-1절 검증 트리거 : 훅보다 원자료 확인이 먼저 ─────────────────────────
_VERIFY_TERMS = (
    "의약품", "부작용", "오남용", "처방", "복용", "백신", "치료제", "임상", "발암",
    "위고비", "마운자로", "다이어트약", "영양제",
    "투자", "수익률", "주식", "코인", "배당", "청약", "대출금리",
    "확정", "지정", "규제", "고시", "발표",
)
_VERIFY_PATTERNS = (
    re.compile(r"\d+\s*배\s*(?:증가|위험|상승)"),
    re.compile(r"위험\s*\d"),
    re.compile(r"전세계에서 가장|세계 최초|국내 최초"),
)

# ── 7절 계정 분기 : @biojuho는 저장형·해석형만 ────────────────────────────
_TONE_CLASH_TERMS = ("ㅅㅂ", "ㅈ같", "개쳐", "미친", "실화냐", "레전드", "핵")
_TONE_CLASH_PATTERNS = (re.compile(r"[?？]{2,}"), re.compile(r"[ㅋㅎ]{3,}"))

AXIS_LABELS = {
    "live_wrong": "사는 축① 가해자 명확",
    "live_gap": "사는 축② 낙차·반전",
    "dead_debate": "죽는 축① 쌍방 논쟁",
    "dead_flat": "죽는 축② 낙차 약함",
    "unknown": "원문 확인 필요",
}


def _hits(text: str, terms: tuple[str, ...]) -> list[str]:
    return [t for t in terms if t.casefold() in text]


def _screen_material_text(title: str, *, community_label: str | None = None) -> dict[str, Any]:
    """제목 한 줄로 커널 소재 축을 근사한다. 확정이 아니라 선별 보조다."""
    raw = " ".join(str(title or "").split())
    text = raw.casefold()
    if not text:
        return {
            "axis": "unknown",
            "axis_label": AXIS_LABELS["unknown"],
            "person": False,
            "person_terms": [],
            "verify_first": False,
            "tone_clash": False,
            "signals": [],
            "confidence": "low",
        }

    signals: list[str] = []

    verify = _hits(text, _VERIFY_TERMS) + [
        p.pattern for p in _VERIFY_PATTERNS if p.search(text)
    ]
    if verify:
        signals.append(f"검증 어휘 {verify[0]}")

    tone = _hits(text, _TONE_CLASH_TERMS) + [
        "물음표 반복" if p.pattern.startswith("[?") else "자음 반복"
        for p in _TONE_CLASH_PATTERNS
        if p.search(raw)
    ]

    debate = _hits(text, _DEBATE_TERMS)
    debate_q = [p for p in _DEBATE_PATTERNS if p.search(raw)]
    actors = _hits(text, _ACTOR_TERMS)
    wrongs = _hits(text, _WRONGDOING_TERMS)
    gaps = _hits(text, _GAP_TERMS + _WEAK_GAP_TERMS) + [name for p, name in _GAP_PATTERNS if p.search(text)]

    # 판정 순서가 곧 우선순위다. 가해자와 논쟁 신호가 함께 있으면 논쟁이 이긴다 —
    # 독자 판단이 갈리는 순간 인용 방향이 모이지 않기 때문이다.
    if debate or debate_q:
        axis = "dead_debate"
        if debate:
            signals.append(f"논쟁 신호 '{debate[0]}'")
        if debate_q:
            signals.append("판단을 되묻는 종결")
        confidence = "medium"
    elif actors and wrongs:
        axis = "live_wrong"
        signals.append(f"가해 역할 '{actors[0]}' + 행위 '{wrongs[0]}'")
        confidence = "medium"
    elif gaps:
        # 0011: 약한 어휘("이유"·"근황")만 있고 강한 신호가 없으면 unknown.
        # "식당이 휴가를 간 이유"는 _GAP_PATTERNS의 서사 이유(⑥)가 먼저 잡아
        # strong_gaps에 들어가므로 live_gap 유지. "옷차림이 중요해지는 이유"는
        # 강한 신호 없고 서사 패턴도 안 맞아 unknown으로 내려간다.
        strong_gaps = [g for g in gaps if g not in _WEAK_GAP_TERMS]
        if strong_gaps:
            axis = "live_gap"
            signals.append(f"낙차 신호 '{strong_gaps[0]}'")
            confidence = "low"
        else:
            axis = "unknown"
            signals.append(f"'{gaps[0]}'만으로는 낙차를 확정할 수 없음 — 원문에서 확인")
            confidence = "low"
    elif actors:
        axis = "unknown"
        signals.append(f"역할 '{actors[0]}'은 있으나 행위가 드러나지 않음")
        confidence = "low"
    elif len(re.sub(r"\W", "", raw)) < 8:
        # 신호가 하나도 없는데 입력까지 짧다. X 레이더는 제목이 아니라 검색어 한 단어를
        # 준다("김혜수", "오디세이") — 그걸 "낙차 약함"으로 단정하면 판정처럼 보이는
        # 착시만 만든다. 모르면 모른다고 한다.
        axis = "unknown"
        signals.append("단어만 있어 소재 축을 판정할 수 없음 — 원문에서 확인")
        confidence = "low"
    else:
        axis = "dead_flat"
        signals.append("가해·낙차 신호 없음")
        confidence = "low"

    if tone:
        signals.append(f"@biojuho 톤 충돌 '{tone[0]}'")

    return {
        "axis": axis,
        "axis_label": AXIS_LABELS[axis],
        "person": bool(actors),
        "person_terms": actors[:3],
        "verify_first": bool(verify),
        "tone_clash": bool(tone),
        "signals": signals,
        "confidence": confidence,
    }


def screen_material(
    title: str,
    *,
    community_label: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """근사 판정하되, 제목이 약할 때만 원문 OG 요약으로 2차 판정한다.

    ``summary``는 응답이나 저장소에 싣지 않는다. 판정이 바뀌면 원문에서 확인한
    근거라는 사실만 signals에 남긴다. 제목 전용 호출은 기존과 완전히 동일하다.
    """
    title_result = _screen_material_text(title, community_label=community_label)
    normalized_summary = " ".join(str(summary or "").split())
    if not normalized_summary:
        return title_result
    if title_result["axis"] not in {"dead_flat", "unknown"}:
        summary_actors = _hits(normalized_summary.casefold(), _ACTOR_TERMS)
        if not title_result["person"] and summary_actors:
            result = dict(title_result)
            result["person"] = True
            result["person_terms"] = summary_actors[:3]
            result["person_source"] = "summary"
            return result
        return title_result

    combined = f"{title} {normalized_summary}".strip()
    second_result = _screen_material_text(combined, community_label=community_label)
    summary_wrongs = _hits(normalized_summary.casefold(), _WRONGDOING_TERMS)
    named_warning = bool(
        re.search(r"[A-Za-z]{2,}", str(title or ""))
        and re.search(r"(?:하지|타지|먹지|사지|쓰지|가지)\s*마세요|(?:주의|조심)", str(title or ""))
    )
    if summary_wrongs and named_warning and second_result["axis"] in {"dead_flat", "unknown"}:
        second_result["axis"] = "live_wrong"
        second_result["axis_label"] = AXIS_LABELS["live_wrong"]
        second_result["signals"] = [
            "원문 첫 문단에서 명명된 경고 대상과 피해 행위 확인",
            f"피해 행위 '{summary_wrongs[0]}'",
        ]
        second_result["confidence"] = "medium"
    # person은 기존 5축과 독립이다. 요약에서 person만 새로 잡혔다고 기존 signals까지
    # "원문 확인"으로 바뀌면 병기가 아니라 판정 변경이 되므로, 기존 필드만 대조한다.
    legacy_fields = (
        "axis", "axis_label", "verify_first", "tone_clash", "signals", "confidence",
    )
    legacy_result_changed = any(
        second_result[field] != title_result[field] for field in legacy_fields
    )
    person_from_summary = not title_result["person"] and second_result["person"]
    if not legacy_result_changed:
        if person_from_summary:
            second_result["person_source"] = "summary"
            return second_result
        return title_result

    evidence_by_axis = {
        "live_wrong": "원문 첫 문단에서 가해 역할과 행위 확인",
        "live_gap": "원문 첫 문단에서 낙차·반전 확인",
        "dead_debate": "원문 첫 문단에서 쌍방 논쟁 구조 확인",
        "dead_flat": "원문 첫 문단에도 가해·낙차 신호 없음",
        "unknown": "원문 첫 문단까지 봐도 소재 축 불명확",
    }
    if not second_result["signals"] or not second_result["signals"][0].startswith("원문 첫 문단"):
        second_result["signals"] = [
            evidence_by_axis[second_result["axis"]],
            *second_result["signals"],
        ]
    if second_result["verify_first"] and not title_result["verify_first"]:
        second_result["signals"].append("원문 첫 문단에서 검증 필요 정보 확인")
    if person_from_summary:
        second_result["person_source"] = "summary"
    return second_result


# 정렬 우선순위 상수. 연구 재현용으로 보존한다.
# 2026-08-08 실측에서 live_wrong/live_gap/dead_debate/dead_flat 네 축이 기각되어
# 생산 정렬에서는 사용하지 않는다.
_AXIS_RANK = {"live_wrong": 0, "live_gap": 1, "unknown": 2, "dead_debate": 3, "dead_flat": 4}


def sort_by_kernel_legacy_axis(items: list[Any]) -> list[Any]:
    """연구 재현용: 2026-08-08 이전 _AXIS_RANK를 3차 키로 쓰던 정렬."""
    def key(item: Any) -> tuple[int, int, int, float]:
        if not isinstance(item, dict):
            return (9, 9, 9, 0.0)
        kernel = item.get("kernel_screen") or {}
        axis = kernel.get("axis", "unknown")
        try:
            score = float(item.get("x_exposure_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        return (
            0 if kernel.get("person") is True else 1,
            1 if item.get("cooling") is True else 0,
            _AXIS_RANK.get(axis, 2),
            -score,
        )

    return sorted(items, key=key)


def sort_by_kernel(items: list[Any]) -> list[Any]:
    """person, 식음 여부, 적합도 점수 순으로 정렬한다.

    2026-08-16 0062 핸드오프: 검정 통과 근거가 없는 _AXIS_RANK를 생산 정렬에서 제거함.
    남는 정렬 키:
    1차: person 여부 (True가 앞)
    2차: cooling 여부 (False(0)가 앞, True(1)가 뒤)
    3차: x_exposure_score 점수 (내림차순, 큰 값이 앞)
    동점 시: stable sort (입력 원래 순서 보존)
    """
    def key(item: Any) -> tuple[int, int, float]:
        if not isinstance(item, dict):
            return (9, 9, 0.0)
        kernel = item.get("kernel_screen") or {}
        try:
            score = float(item.get("x_exposure_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        return (
            0 if kernel.get("person") is True else 1,
            1 if item.get("cooling") is True else 0,
            -score,
        )

    return sorted(items, key=key)


def attach_kernel_screen(
    payload: dict[str, Any], *, title_field: str = "title", sort: bool = True
) -> dict[str, Any]:
    """스냅샷 응답의 items 각각에 kernel_screen을 얹는다(원본은 건드리지 않는다)."""
    enriched = dict(payload or {})
    items = enriched.get("items")
    if not isinstance(items, list):
        return enriched
    screened = []
    for item in items:
        if not isinstance(item, dict):
            screened.append(item)
            continue
        copy = dict(item)
        existing_screen = copy.get("kernel_screen")
        if isinstance(existing_screen, dict) and existing_screen.get("axis") in AXIS_LABELS:
            screen = dict(existing_screen)
            if "person" not in screen or "person_terms" not in screen:
                title_screen = _screen_material_text(
                    copy.get(title_field, ""), community_label=copy.get("community_label")
                )
                screen.setdefault("person", title_screen["person"])
                screen.setdefault("person_terms", title_screen["person_terms"])
            copy["kernel_screen"] = screen
        else:
            copy["kernel_screen"] = screen_material(
                copy.get(title_field, ""), community_label=copy.get("community_label")
            )
        screened.append(copy)
    if sort:
        screened = sort_by_kernel(screened)
    enriched["items"] = screened
    # 선별을 돕는 요약 — 목록 위에서 "지금 쓸 만한 게 몇 개인지"가 바로 보이게.
    enriched["kernel_summary"] = {
        "live": sum(1 for i in screened if isinstance(i, dict) and i.get("kernel_screen", {}).get("axis", "").startswith("live")),
        "dead": sum(1 for i in screened if isinstance(i, dict) and i.get("kernel_screen", {}).get("axis", "").startswith("dead")),
        "verify_first": sum(1 for i in screened if isinstance(i, dict) and i.get("kernel_screen", {}).get("verify_first")),
        "person_count": sum(1 for i in screened if isinstance(i, dict) and i.get("kernel_screen", {}).get("person") is True),
    }
    return enriched
