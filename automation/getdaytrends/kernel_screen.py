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
    "남편", "아내", "시어머니", "시아버지", "시댁", "친정", "장모", "며느리",
    "팀장", "부장", "상사", "선배", "후배", "동료", "직원",
    "손님", "진상", "윗집", "아랫집", "집주인", "세입자",
    "택배", "점주", "원장", "교수", "담임", "학부모", "친구", "지인",
    "남친", "여친", "전남친", "전여친", "엄마", "아빠", "부모", "오빠", "누나", "동생",
    "와이프", "유부남", "유부녀",
    # 0070(2026-08-16): 관계·직함 확장. 헤더 실측에서 제목에 관계·직함이 있는데
    # person=False였던 3건("군인 가능"·"대구 선생님들 이리 와봐요"·"하영 증조모 … 딸?")을
    # 메운다. person은 이 계정에서 유일하게 검정을 통과한 축이라 놓침은 곧 후보 감소다.
    # 0070 주석의 「shadow 13,800 전수에서 하위문자열 오탐 0건」은 그때 추가한
    # 어휘에 한정된다. 형·사장·과장·군인·고객·이웃·알바·기사·장인·사위는 원래
    # 목록이라 경계 검사를 받은 적이 없었고, 0080에서 코퍼스 문맥을 열어
    # _ACTOR_BOUNDARY_PATTERNS 로 옮겼다. 손주는 야구선수 손주영과 충돌해
    # 넣지 않았다(손자·손녀가 증손자·증손녀까지 덮는다).
    "할머니", "할아버지", "증조모", "증조부", "조카", "손녀", "삼촌", "고모", "숙모",
    "선생", "장교", "훈련병",
    # 0080(2026-08-18): 뉴스 제목에서 눈으로 확인한 관계·역할. 각 어휘는
    # shadow unique 제목 전수에서 오탐 문맥을 먼저 열람하고, 오탐이 나온
    # 것은 경계로 돌리거나 빼 두었다. 배우·가수·감독·기자·작가는 커뮤니티
    # 적중이 커 비율을 ±1%p 밖으로 밀고(시뮬 +2%p), 감독은 「감독기구·
    # 집중감독·고강도 감독」이 검사/기관이라 넣지 않았다. 의원·장관·대통령·
    # 목사 류는 정치·종교 금지.
    "모친", "부친", "유족", "유가족", "언론인",
    "여고생", "남고생", "중학생", "초등학생", "고등학생",
    "20대", "30대", "40대", "50대", "60대", "70대",
    "보행자", "피해자", "직장인",
)

# 0070·0080: 경계가 필요한 관계어. 한국어는 띄어쓰기가 불안정해 순수 부분문자열로
# 넣으면 사람 아닌 낱말이 함께 걸린다(0048의 친일 어간 사례와 같은 원리, 방향은 반대).
# 배제 집합은 shadow unique 제목에서 해당 어휘의 등장 맥락을 전수 열람해 정했다.
# - 딸: 딸기·딸리다(딸려·딸린)·딸배·딸치다·딸잽이·"번호 딸까"·딸랑·딸맨은 사람이 아니고,
#   앞글자 리(리딸)도 사람이 아니다. 딸딸이는 두 번째 딸이 뒤에 '이'가 와서 lookahead만
#   골라내지지 않는다 — lookbehind((?<!딸))로 앞 딸도 함께 막는다.
# - 아들: 알아들다·받아들이다 안의 "아들"만 사람이 아니다(각 4건·4건). 어근이
#   알+아들·받+아들로 붙어 있어 lookbehind는 한 글자(알·받)로 본다. 수양아들·
#   친아들 같은 실제 형태는 앞글자가 달라 그대로 잡힌다.
# - 손자: 손자병법(책)은 손자(孫子)라도 관계어가 아니다.
# - 이모: 이모티콘·이모지·이모션.
# - 교사: 반면교사(관용구). 살인교사 류의 敎唆 감각은 코퍼스에 0건이었다.
# - 형(0080): 한 글자라 -形/-刑/-型 접미를 전부 먹는다. 뉴스 person 112건 중
#   36건이 ["형"] 단독이었고 표본 전부가 오탐(맞춤형·사형 구형·징역형·대형·
#   신형·김주형·전형·형제·형소법). 접두 배제는 코퍼스 윈도우에서 모았다.
#   형님·친형·큰형·「청래형」같은 호칭은 접두 목록 밖이라 유지된다.
# - 사장: 공사장(공사 현장 4건)·역사장사꾼(장사 1건). 이사장은 사람(유지).
# - 과장: 허위과장(광고 3건). 「과장이나 호들갑」1건은 어휘 자체가 허위라
#   접두만으로는 못 가른다 — 직함 과장을 죽이면 실패라 남긴다.
# - 군인: 아군인줄(1건, 우리 편). 제대군인은 사람이다.
# - 고객: 고객추천(광고 3)·고객만족도(2)·고객센터(1).
# - 이웃: 이웃나라·이웃돕기. 이웃집은 사람이다.
# - 알바: 알바레스(선수명 2건).
# - 기사: [기사] 태그·나기사(캐릭터)·아기사자. 택시기사·기사님은 유지.
#   0104: 기사(article) 메타 문구는 아래 문맥 패턴으로 한 번 더 거른다.
# - 장인: 직장인(직+장인)·등장인물(등+장인). 직장인은 별도 사전 항.
# - 사위: 조사위·법사위(위원회). 데릴사위·예비 사위는 유지.
# - 선수: 세계선수권·선수권대회(대회명 25건). 선수단은 사람이다.
# - 운전자: 운전자보험(광고).
# - 10대: 제10대(대수)·10대 대표브랜드(순위). 연령 10대는 유지.
# - 80대: 「방제설비 80대 운영」은 대수(臺)이지 나이가 아니다.
_ACTOR_BOUNDARY_PATTERNS = (
    (re.compile(r"(?<![리딸])딸(?!기|리|린|딸|배|치|잽|까|랑|맨|깍|꾹)"), "딸"),
    (re.compile(r"(?<!알)(?<!받)아들"), "아들"),
    (re.compile(r"손자(?!병)"), "손자"),
    (re.compile(r"이모(?!티|지|션)"), "이모"),
    (re.compile(r"(?<!반면)교사"), "교사"),
    (
        re.compile(
            r"(?<!대)(?<!소)(?<!중)(?<!신)(?<!구)(?<!사)(?<!유)(?<!인)(?<!전)(?<!원)"
            r"(?<!모)(?<!도)(?<!정)(?<!무)(?<!태)(?<!처)(?<!년)"
            r"(?<!벌금)(?<!징역)(?<!초대)(?<!이상)(?<!오픈)(?<!맞춤)"
            r"(?<!참여)(?<!실행)(?<!체류)(?<!공격)(?<!생성)(?<!현장)"
            r"(?<!생계)(?<!논술)(?<!서술)(?<!밀착)(?<!불균)(?<!골목)"
            r"(?<!김주)(?<!여인)(?<!양세)(?<!박준)(?<!심)"
            r"형(?!사|소법|제|벌|태|식|상|래|묵)"
        ),
        "형",
    ),
    (re.compile(r"(?<!공)(?<!역)사장"), "사장"),
    (re.compile(r"(?<!허위)과장"), "과장"),
    (re.compile(r"(?<!아)군인"), "군인"),
    (re.compile(r"고객(?!추천|만족|센터)"), "고객"),
    (re.compile(r"이웃(?!나라|돕기)"), "이웃"),
    (re.compile(r"알바(?!레스)"), "알바"),
    (re.compile(r"(?<!나)(?<!\[)(?<!아)기사"), "기사"),
    (re.compile(r"(?<!직)(?<!등)장인"), "장인"),
    (re.compile(r"(?<!조)(?<!법)사위"), "사위"),
    (re.compile(r"선수(?!권)"), "선수"),
    (re.compile(r"운전자(?!보험)"), "운전자"),
    (re.compile(r"(?<!제)10대(?!\s*대표)"), "10대"),
    (re.compile(r"80대(?!\s*운영)"), "80대"),
)

# 0104(2026-08-31): 「기사」는 뉴스 article과 운전 직무가 동형이다. 사전에서 지우면
# 「택시 기사가 승객을 두고 갔다」까지 죽으므로, 명시적인 운전 직무·존칭은 보존하고
# 매체명 또는 article 보일러플레이트와 붙은 경우만 person에서 제외한다.
_DRIVER_ARTICLE_CONTEXT_PATTERN = re.compile(
    r"(?:택시|버스|운전|화물|배달|대리|트럭|콜밴)\s*기사"
    r"|기사(?:님|분)(?=(?:이|가|은|는|을|를|에게|께서|도|만|과|와|의|들이?|랑)?(?:\s|$|[,.!?…'\"()]))"
)
_MEDIA_ARTICLE_CONTEXT_PATTERN = re.compile(
    r"[가-힣a-z0-9]+(?:일보|신문|뉴스|통신|방송|미디어|저널|타임스)\s*(?:의\s*)?기사"
    r"|기사\s*(?:제공|안내|저작권|무단\s*전재|재배포|재전송|콘텐츠|원문|전문|보기|출처)"
    r"|(?:저작권|콘텐츠|무단\s*전재|재배포|재전송|출처|제공\s*자료|보도\s*자료).{0,8}기사"
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
# ── 육성 한 줄 (2026-08-23) ────────────────────────────────────────────────
# 제목의 따옴표가 «옮겨 쓸 수 있는 발화»인지 본다. 따옴표만으로는 못 가른다 —
# 2026-08-23 홀드아웃 19건에서 «따옴표만» 규칙의 정밀도가 65.5%→28.6%로 반토막 났다.
# 서울시 보도자료의 행사명('푸른하늘의 날')·정책명('쾌속통합')·브랜드('모두의 AI')가
# 전부 따옴표를 쓰기 때문이다. 그래서 안쪽이 «말»인지를 어미·호격으로 한 번 더 본다.
# 그 2차 조건을 붙이면 같은 홀드아웃에서 정밀도·재현율이 둘 다 100%가 됐다(n=19, 양성 2).
_QUOTE_RE = re.compile(r"[\"“”'‘’]([^\"“”'‘’]{1,60})[\"“”'‘’]")
_QUOTE_ENDING_RE = re.compile(
    r"(요|다|냐|까|임|음|하자|어|네|지|야|죠|군|걸|나|래|든|거든|잖아)[?!.…~]*$"
)
_QUOTE_VOCATIVE_RE = re.compile(r"(님|왜|어디|우리|저희|제가|내가)")

_TONE_CLASH_TERMS = ("ㅅㅂ", "ㅈ같", "개쳐", "미친", "실화냐", "레전드", "핵")
_TONE_CLASH_PATTERNS = (re.compile(r"[?？]{2,}"), re.compile(r"[ㅋㅎ]{3,}"))

AXIS_LABELS = {
    "live_wrong": "사는 축① 가해자 명확",
    "live_gap": "사는 축② 낙차·반전",
    "dead_debate": "죽는 축① 쌍방 논쟁",
    "dead_flat": "죽는 축② 낙차 약함",
    "unknown": "원문 확인 필요",
}


def has_quote_line(title: str) -> bool:
    """옮겨 쓸 수 있는 육성 한 줄이 제목에 있는가.

    따옴표 안이 4자 이상이고, 구어체 종결어미로 끝나거나 호격·1인칭이 들어 있어야 한다.
    행사명·정책명·브랜드명은 이 조건에서 걸러진다.
    """
    for m in _QUOTE_RE.finditer(str(title or "")):
        inner = m.group(1).strip()
        if len(inner) >= 4 and (
            _QUOTE_ENDING_RE.search(inner) or _QUOTE_VOCATIVE_RE.search(inner)
        ):
            return True
    return False


def _hits(text: str, terms: tuple[str, ...]) -> list[str]:
    return [t for t in terms if t.casefold() in text]


def require_actor_lexicon() -> None:
    """person 측정은 사전이 비면 오탐 0으로 접지 않고 실패한다.

    `_ACTOR_TERMS`와 경계 패턴을 둘 다 비우면 모든 제목이 person=False가 되어
    나이브한 집계가 「오탐 0」을 보고한다. 부재는 성공이 아니라 제3의 결과다.
    """
    if not _ACTOR_TERMS and not _ACTOR_BOUNDARY_PATTERNS:
        raise RuntimeError("person lexicon is empty — refuse to report zero false positives")


def _actor_hits(text: str) -> list[str]:
    """person 어휘 = 부분문자열 사전 + 경계 패턴을 합친다(중복 제거, 사전 순서 우선).

    text는 호출 쪽에서 이미 casefold한 값이다(제목·요약 두 경로 모두 그렇다).
    """
    hits = _hits(text, _ACTOR_TERMS)
    for pattern, term in _ACTOR_BOUNDARY_PATTERNS:
        if term in hits or not pattern.search(text):
            continue
        if (
            term == "기사"
            and not _DRIVER_ARTICLE_CONTEXT_PATTERN.search(text)
            and _MEDIA_ARTICLE_CONTEXT_PATTERN.search(text)
        ):
            continue
        hits.append(term)
    return hits


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
            "quote_line": False,
            "verdict_split": "?",
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
    actors = _actor_hits(text)
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

    # 2026-08-23. 아래 둘은 «표시»지 «제외»가 아니다. 축(axis)도 정렬도 바꾸지 않는다.
    # 규칙이 아직 약해서 막으면 소재가 소리 없이 사라진다.
    #
    # verdict_split 이 dead_debate 축과 어긋나 보이는 것은 모순이 아니다.
    # 축은 «도달»을 재고(커널 실측에서 논쟁 축은 도달 예측에 기각됐다)
    # 이 필드는 «답글»을 잰다. 2026-08-23 실측 — 계정 안에서 답글율 1위 글의
    # 노출이 2,800이다. 답글 처방과 도달 처방은 같은 처방이 아니다.
    verdict_split = "Y" if (debate or debate_q or (actors and wrongs)) else "?"

    return {
        "axis": axis,
        "axis_label": AXIS_LABELS[axis],
        "person": bool(actors),
        "person_terms": actors[:3],
        "verify_first": bool(verify),
        "tone_clash": bool(tone),
        "quote_line": has_quote_line(raw),
        "verdict_split": verdict_split,
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
        summary_actors = _actor_hits(normalized_summary.casefold())
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
            raw_summary = copy.get("summary")
            summary = raw_summary if isinstance(raw_summary, str) and raw_summary.strip() else None
            copy["kernel_screen"] = screen_material(
                copy.get(title_field, ""),
                community_label=copy.get("community_label"),
                summary=summary,
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
