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
)

_WRONGDOING_TERMS = (
    "갑질", "떠넘", "뺏", "강요", "무시", "방치", "폭언", "욕설", "협박", "바가지",
    "몰래", "무단", "속이", "속였", "거짓말", "잠수", "먹튀", "안 준", "안 줬", "안줌",
    "밀린", "체불", "미지급", "손절", "차별", "부당", "억지", "진상짓", "새치기",
)

# ── 5-1절 사는 축② : 가해자 없는 강한 낙차 ────────────────────────────────
_GAP_TERMS = (
    "알고 보니", "알고보니", "반전", "뜻밖", "사실은", "정체", "이유", "결말", "근황",
    "충격", "소름", "레전드", "기적", "실화", "이럴 수가", "예상 밖", "예상밖",
    # 역접이 곧 낙차다. 2026-08-06에 "장사가 너무 잘돼서, 오히려 망했다"(노출 3위)를
    # 낙차 없음으로 오판해 추가했다.
    "오히려", "도리어", "인데도", "줄 알았는데", "줄알았는데", "그런데 정작", "했는데 정작",
    "안 했는데", "했더니", "하자마자",
)

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


def screen_material(title: str, *, community_label: str | None = None) -> dict[str, Any]:
    """제목 한 줄로 커널 소재 축을 근사한다. 확정이 아니라 선별 보조다."""
    raw = " ".join(str(title or "").split())
    text = raw.casefold()
    if not text:
        return {
            "axis": "unknown",
            "axis_label": AXIS_LABELS["unknown"],
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
    gaps = _hits(text, _GAP_TERMS) + [name for p, name in _GAP_PATTERNS if p.search(text)]

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
        axis = "live_gap"
        signals.append(f"낙차 신호 '{gaps[0]}'")
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
        "verify_first": bool(verify),
        "tone_clash": bool(tone),
        "signals": signals,
        "confidence": confidence,
    }


def attach_kernel_screen(payload: dict[str, Any], *, title_field: str = "title") -> dict[str, Any]:
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
        copy["kernel_screen"] = screen_material(
            copy.get(title_field, ""), community_label=copy.get("community_label")
        )
        screened.append(copy)
    enriched["items"] = screened
    # 선별을 돕는 요약 — 목록 위에서 "지금 쓸 만한 게 몇 개인지"가 바로 보이게.
    enriched["kernel_summary"] = {
        "live": sum(1 for i in screened if isinstance(i, dict) and i.get("kernel_screen", {}).get("axis", "").startswith("live")),
        "dead": sum(1 for i in screened if isinstance(i, dict) and i.get("kernel_screen", {}).get("axis", "").startswith("dead")),
        "verify_first": sum(1 for i in screened if isinstance(i, dict) and i.get("kernel_screen", {}).get("verify_first")),
    }
    return enriched
