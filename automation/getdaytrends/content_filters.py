"""Shared topic exclusions for the live source dashboards."""

from __future__ import annotations

import re


_SPORTS_TERMS = (
    "축구",
    "야구",
    "농구",
    "배구",
    "골프",
    "테니스",
    "핸드볼",
    "탁구",
    "배드민턴",
    "e스포츠",
    "이스포츠",
    "리그오브레전드",
    "리그 오브 레전드",
    "롤드컵",
    "롤)",
    "lck",
    "올림픽",
    "월드컵",
    "챔피언스리그",
    "챔스",
    "프리미어리그",
    "분데스리가",
    "라리가",
    "세리에a",
    "k리그",
    "kbo",
    "mlb",
    "nba",
    "epl",
    "uefa",
    "afc",
    "klpga",
    "kpga",
    "lpga",
    "pga투어",
    "ufc",
    "wbc",
    "psg",
    "파리 생제르맹",
    "아스날",
    "토트넘",
    "맨체스터 유나이티드",
    "맨체스터 시티",
    "맨유",
    "맨시티",
    "리버풀",
    "첼시",
    "바르셀로나",
    "레알 마드리드",
    "마요르카",
    "손흥민",
    "김하성",
    "김병지",
    "이정후",
    "임종언",
    "류현진",
    "오타니",
    "홈런",
    "안타",
    "타선",
    "타격",
    "포구",
    "송구",
    "끝내기",
    "완패",
    "쇼트트랙",
    "도핑 징계",
    "투수",
    "타자",
    "득점",
    "이적설",
    "연장전",
    "승부차기",
    "프로야구",
    "프로축구",
)

_MARKET_TERMS = (
    "코스피",
    "코스닥",
    "나스닥",
    "다우지수",
    "다우 존스",
    "s&p 500",
    "s&p500",
    "증시",
    "증권가",
    "증권사",
    "주식",
    "주가지수",
    "선물지수",
    "야간선물",
    "야선",
    "프리장",
    "애프터장",
    "상한가",
    "하한가",
    "시가총액",
    "목표주가",
    "급등주",
    "급락주",
    "공모주",
    "주식시장",
    "주식 투자",
    "외국인 순매수",
    "기관 순매수",
    "매수세",
    "매도세",
    "배당주",
    "배당금",
    "etf",
    "레버리지",
    "adr",
    "필라델피아 반도체",
    "유상증자",
    "자본조달",
    "어닝 서프라이즈",
    "어닝 쇼크",
    "실적 발표",
    "분기 실적",
    "실적",
    "영업익",
    "영업이익",
    "당기순이익",
    "순이익",
    "매출액",
    "컨센서스",
    "흑자",
    "적자",
    "ipo",
    "nasdaq",
    "nyse",
    "stock market",
    "market outlook",
    "analyst target",
    "nvda",
    "tsla",
    "금리",
    "환율",
    "국채",
    "비트코인 시세",
    "가상자산 시세",
    "암호화폐 시세",
    "코인 시세",
)

_REAL_ESTATE_TERMS = (
    "부동산",
    "아파트",
    "주택시장",
    "주택 가격",
    "집값",
    "전셋값",
    "전세가",
    "전세금",
    "전세 계약",
    "월세",
    "매매가",
    "실거래가",
    "분양가",
    "분양권",
    "청약",
    "재건축",
    "재개발",
    "갭투자",
    "종부세",
    "취득세",
    "양도세",
    "전세사기",
    "임대차",
    "임대료",
    "오피스텔",
    "공시가격",
    "토지거래허가",
    "주택담보대출",
    "주담대",
)

_POLITICS_TERMS = (
    "정치",
    "대통령",
    "대통령실",
    "국회",
    "국회의원",
    "여당",
    "야당",
    "민주당",
    "국민의힘",
    "조국혁신당",
    "개혁신당",
    "정당",
    "정치권",
    "선거",
    "대선",
    "총선",
    "탄핵",
    "특검",
    "공천",
    "당대표",
    "원내대표",
    "국무총리",
    "개각",
    "국정감사",
    "국정조사",
    "백악관",
    "미 의회",
    "미의회",
    "미 상원",
    "미 하원",
    "공화당",
    "미국 민주당",
    "트럼프",
    "바이든",
    "국무부",
    "외교부",
    "총리",
    "시진핑",
    "푸틴",
    "젤렌스키",
    "김정은",
    "시의원",
    "도의원",
    "구의원",
    "도지사",
    "시장 후보",
    "지자체장",
    "이재명",
    "윤석열",
    "김건희",
    "한동훈",
    "조국",
    "신남성연대",
    "남성연대",
    "민생지원금",
    # 2026-08-06 보배드림을 붙이자 "국짐이 정청래편인척"이 유머게시판 글로 통과했다.
    # 커뮤니티는 정당·정치인을 실명 대신 줄임말·별칭으로 쓴다. 게시판 카테고리로는
    # 거를 수 없어(정치 유머가 유머게시판에 올라온다) 표기 자체를 넓혔다.
    "더불어민주당",
    "국짐",
    "국개의원",
    "정청래",
    "추미애",
    "이준석",
    "홍준표",
    "오세훈",
    "김문수",
    "박찬대",
    "나경원",
    "여의도 정가",
    # 같은 날 라운드에서 실제로 통과한 것들. 이름 목록을 쫓는 방식의 한계를 보여주는 사례이기도
    # 하다 — 새 인물·단체는 계속 생긴다. 대안은 STATE.md의 결정 대기 항목에 적어 두었다.
    "최민희",
    "리박스쿨",
)

_SPORTS_CONTEXT_PATTERNS = (
    re.compile(r"\b[a-z0-9][a-z0-9 .-]{2,}\s+vs\.?\s+[a-z0-9][a-z0-9 .-]{2,}\b"),
    re.compile(r"(?:선수|감독|구단|팀)\s*(?:영입|방출|계약|이적|복귀|은퇴|승리|패배)"),
    re.compile(r"(?:결승|준결승|예선|리그)\s*(?:진출|탈락|경기|우승)"),
    re.compile(r"\d+\s*[-:]\s*\d+\s*(?:승|패|무|종료)"),
    re.compile(r"(?:대회|투어|마스터스).{0,20}(?:우승|준우승|챔피언)"),
)

_MARKET_CONTEXT_PATTERNS = (
    re.compile(r"(?:주가|종목)\s*(?:가|는|도|를|급등|급락|상승|하락|전망)"),
    re.compile(r"(?:매출|실적)\s*(?:발표|전망|개선|악화|증가|감소|급증|급감)"),
    re.compile(r"(?:1|2|3|4)분기\s*(?:매출|실적|영업익|영업이익|순이익)"),
)

_REAL_ESTATE_CONTEXT_PATTERNS = (
    re.compile(r"(?:집|주택)\s*(?:을|를)?\s*(?:샀|사서|산|팔았|판|매수|매도)"),
    re.compile(r"(?:전세|월세)\s*(?:끼고|계약|보증금|대출|시세)"),
)

_POLITICS_CONTEXT_PATTERNS = (
    re.compile(r"(?:정부|장관|의원)\s*(?:발표|추진|비판|반박|사퇴|임명|해임|논란|출마)"),
    re.compile(r"(?:법안|정책)\s*(?:발의|통과|폐기|강행|철회)"),
    re.compile(r"(?:정부|지자체|서울시|경기도|광역시).{0,12}(?:예산|재정|부도|지원금)"),
)


# 성별 갈등 소재. 커뮤니티에서 조회·댓글은 잘 나오지만 X로 옮기면 싸움만 남는다.
# "한남"은 한남동·한남대교·한남대학교와 겹쳐서 단독으로 넣지 않고 갈등 표현만 잡는다.
_GENDER_CONFLICT_TERMS = (
    "페미",
    "패미",
    "페미니즘",
    "페미니스트",
    "메갈",
    "워마드",
    "남혐",
    "여혐",
    "한남충",
    "김치녀",
    "된장녀",
    "군무새",
    "젠더갈등",
    "젠더 갈등",
    "성별 갈등",
    "이대남",
    "이대녀",
)

_GENDER_CONFLICT_CONTEXT_PATTERNS = (
    re.compile(r"(?:남자|여자|남성|여성)\s*(?:vs|대)\s*(?:남자|여자|남성|여성)"),
    re.compile(r"(?:남녀)\s*(?:갈등|대립|싸움|전쟁)"),
)

# 애니메이션·만화 소재. "애니"는 애니팡·애니콜·사람 이름과 겹치므로 단독으로 쓰지 않고
# 뒤에 붙는 말이나 앞뒤 문맥이 애니메이션을 가리킬 때만 잡는다.
_ANIME_TERMS = (
    "애니메이션",
    "애니메이숑",
    "극장판",
    "코믹스",
    "만화책",
    "웹툰",
    "오타쿠",
    "덕후짤",
    "성우 캐스팅",
    "신작 애니",
    "애니 추천",
    "애니 명장면",
    "원작 만화",
    "일본 만화",
    "만화 원작",
)

_ANIME_CONTEXT_PATTERNS = (
    re.compile(r"애니\s*(?:방영|공개|1화|\d+화|시즌|캐릭터|주제가|op|ed|명장면|덕후|보는|봤)"),
    re.compile(r"(?:tva|ova|극장판)\s*\d*(?:화|기|기작)?"),
    re.compile(r"(?:작화|성우|원피스|나루토|귀칼|귀멸의 칼날|주술회전|체인소맨)\b"),
)


def excluded_topic_reason(*values: object) -> str | None:
    """Return the factual exclusion bucket for a topic, if any."""
    haystack = " ".join(str(value or "") for value in values).casefold()
    compact = re.sub(r"\s+", " ", haystack)
    if any(term.casefold() in compact for term in _GENDER_CONFLICT_TERMS):
        return "성별 갈등 제외"
    if any(pattern.search(compact) for pattern in _GENDER_CONFLICT_CONTEXT_PATTERNS):
        return "성별 갈등 제외"
    if any(term.casefold() in compact for term in _ANIME_TERMS):
        return "애니·만화 제외"
    if any(pattern.search(compact) for pattern in _ANIME_CONTEXT_PATTERNS):
        return "애니·만화 제외"
    if any(term.casefold() in compact for term in _SPORTS_TERMS):
        return "스포츠 제외"
    if any(pattern.search(compact) for pattern in _SPORTS_CONTEXT_PATTERNS):
        return "스포츠 제외"
    if any(term.casefold() in compact for term in _POLITICS_TERMS):
        return "정치 제외"
    if any(pattern.search(compact) for pattern in _POLITICS_CONTEXT_PATTERNS):
        return "정치 제외"
    if any(term.casefold() in compact for term in _MARKET_TERMS):
        return "증시·실적 제외"
    if any(pattern.search(compact) for pattern in _MARKET_CONTEXT_PATTERNS):
        return "증시·실적 제외"
    if any(term.casefold() in compact for term in _REAL_ESTATE_TERMS):
        return "부동산 제외"
    if any(pattern.search(compact) for pattern in _REAL_ESTATE_CONTEXT_PATTERNS):
        return "부동산 제외"
    return None


def topic_is_allowed(*values: object) -> bool:
    return excluded_topic_reason(*values) is None
