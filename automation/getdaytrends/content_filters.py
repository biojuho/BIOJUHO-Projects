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
    "nfl",
    "nhl",
    "wnba",
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
    "이임생",
    "홍명보",
    "김민재",
    "김하성",
    "김병지",
    "이정후",
    "임종언",
    "류현진",
    "오타니",
    "홈런",
    "타선",
    "포구",
    "끝내기",
    "쇼트트랙",
    "도핑 징계",
    "투수",
    "득점",
    "이적설",
    "연장전",
    "승부차기",
    "프로야구",
    "프로축구",
    "pro bowl",
    "all-star game",
    "premier league",
    "champions league",
    "american football",
    # 2026-08-27 x-radar 실응답 누출(shadow store 실측). 구단·리그명 없이 야구
    # 기록어만으로 통과한 KBO 표본(만루의 사나이·무사만루·만루포·타율·그랜드슬램),
    # 배드민턴 안세영, 축구 홀란, 그리고 «국내 유일 돔구장» 야구장 사건 표본.
    # 만 루(滿壘)·타율·그랜드슬램은 한국어에서 야구·스포츠 기록어로만 쓰인다.
    "만루",
    "무사만루",
    "타율",
    "그랜드슬램",
    "홀란",
    "안세영",
    "돔구장",
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
    "영업익",
    "영업이익",
    "당기순이익",
    "순이익",
    "매출액",
    "컨센서스",
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
    # 2026-08-27 x-radar·fast-viral 실응답 누출. 잭슨홀·연준의장·통화정책 제목과
    # 보험사 순익 9조·"매출 최적화" 인터뷰·"매출 9조 잭팟"이 통과했다. 통화정책·
    # 순익·매출·관세는 한국어에서 기업·시장 문맥으로만 쓰인다.
    "연준",
    "통화정책",
    "잭슨홀",
    "순익",
    "매출",
    "관세",
    "무역전쟁",
    "무역 전쟁",
)

_REAL_ESTATE_TERMS = (
    "부동산",
    "주택시장",
    "주택 가격",
    "집값",
    "전셋값",
    "전세가",
    "전세금",
    "전세 계약",
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

# 블랙리스트는 원리상 새 표현마다 계속 뚫린다. 근본 선별은 0030의 person 같은
# 허용 기준이 맡고, 이 목록은 최후 방어선으로만 유지한다.
_POLITICS_TERMS = (
    "정치",
    "대통령",
    "대통령실",
    "선관위",
    "선거관리위원회",
    "국회",
    "국회의원",
    "국회의장",
    "국회부의장",
    "시의회",
    "도의회",
    "구의회",
    "군의회",
    "상임위",
    "국정감사장",
    "청와대",
    "정부여당",
    "여당",
    "야당",
    "야권",
    "여권",
    "여야",
    "민주당",
    "국민의힘",
    "조국혁신당",
    "개혁신당",
    "정당",
    "정치권",
    "정계",
    "선거",
    "대선",
    "총선",
    "탄핵",
    "특검",
    "공천",
    "당대표",
    "원내대표",
    "국무총리",
    "장관",
    "차관",
    "교육감",
    "군수",
    "구청장",
    "당대변인",
    "대변인",
    "의원실",
    "보좌관",
    "개각",
    "국정감사",
    "국정조사",
    "지지율",
    "공약",
    "발의",
    "개헌",
    "국정운영",
    "정책토론",
    "여론조사",
    "규탄대회",
    "장외집회",
    "대정부질문",
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
    "김민석",
    "정동영",
    "우원식",
    # 2026-08-27 fast-viral IssueLink 실응답 누출. 정치유머 게시판 원문이
    # 게시판 라벨 없이 들어오므로, 제목에 드러난 정치인 이름을 기존 실명 계약에 추가한다.
    "민형배",
    # 2026-08-14 공급 진단: shadow 10,825건에서 친일 포함 행이 allow 119 / block 190으로
    # 갈렸다. 친일파·"친일 청산"만 막아 "친일 매국노"·"친일 성향"·붙여쓴 "친일청산"이 통과했다.
    # 친일은 2음절 합성어라 친일이 아닌 낱말에 하위문자열로 들어가는 경우가 코퍼스에 0건이라
    # 어간을 통째로 넣는다(공백 너머 "친 일"은 한국어 표기상 붙여쓰지 않으니 안 걸린다).
    "친일",
    "친일파",
    "친일 청산",
    "역사 왜곡",
    # 2026-08-27 x-radar 실응답 누출. 정부 AI 윤리원칙·대법관 제청 파장·북한
    # 발사체·최저임금법·극우 음모론자 배상 판결이 통과했다. "정부"는 기존 문맥
    # 패턴(정부+발표/추진…)이 잡던 것과 같은 성격의 정책 소식이므로 어간으로
    # 넣는다. "법원"은 안 넣는다 — 재판·선고 사연은 유효한 사건 소재다(대법원만).
    "정부",
    "북한",
    "대법원",
    "대법관",
    "대법원장",
    "극우",
    "극좌",
    "음모론",
    "독립유공자",
    "최저임금",
)

_SPORTS_CONTEXT_PATTERNS = (
    # 2026-08-06: 부분 문자열 매칭이 "안타깝다"·"정신적 타격"·"송구스럽지만"·"타자기"를
    # 스포츠로 잘라내고 있었다. 실제 스포츠 문맥일 때만 걸리도록 옮긴다.
    re.compile(r"안타\s*(?:를|치|쳤|\d+개|행진)"),
    re.compile(r"타격\s*(?:감|폼|왕|코치|훈련)"),
    re.compile(r"(?:지명|대)?타자\s*(?:로|가|는)\s*(?:출전|나섰|기용)"),
    re.compile(r"\b[a-z0-9][a-z0-9 .-]{2,}\s+vs\.?\s+[a-z0-9][a-z0-9 .-]{2,}\b"),
    re.compile(r"(?:선수|감독|구단|팀)\s*(?:영입|방출|계약|이적|복귀|은퇴|승리|패배)"),
    re.compile(r"(?:결승|준결승|예선|리그)\s*(?:진출|탈락|경기|우승)"),
    re.compile(r"\d+\s*[-:]\s*\d+\s*(?:승|패|무|종료)"),
    # 2026-08-07: "(?:대회|투어|마스터스).{0,20}우승"이 요리·교내 대회까지 스포츠로 잡았다.
    # 실측 "농심배 짜파게티 대회에서 우승한 작품"(X 48만)이 화면 진입 불가가 됐다.
    # 투어·마스터스는 골프 문맥이 강해 유지하고, "대회…우승"은 종목·선수 단서가 있을 때만.
    re.compile(r"(?:투어|마스터스).{0,20}(?:우승|준우승|챔피언)"),
    re.compile(
        r"(?:스포츠|축구|야구|농구|배구|골프|테니스|수영|육상|체조|유도|태권도|"
        r"복싱|권투|씨름|탁구|배드민턴|핸드볼|마라톤|사이클|스키|쇼트트랙|"
        r"올림픽|월드컵|선수권|리그)"
        r".{0,16}대회.{0,20}(?:우승|준우승|챔피언)"
    ),
    re.compile(
        r"대회.{0,12}(?:우승|준우승|챔피언).{0,16}"
        r"(?:선수|구단|국가대표|금메달|은메달|동메달)"
    ),
)

_MARKET_CONTEXT_PATTERNS = (
    re.compile(r"(?:영업|당기|분기|연간|누적)\s*(?:흑자|적자)"),
    re.compile(r"(?:실적)\s*(?:발표|전망|공시|부진|호조)"),
    re.compile(r"(?:주가|종목)\s*(?:가|는|도|를|급등|급락|상승|하락|전망)"),
    re.compile(r"(?:매출|실적)\s*(?:발표|전망|개선|악화|증가|감소|급증|급감)"),
    re.compile(r"(?:1|2|3|4)분기\s*(?:매출|실적|영업익|영업이익|순이익)"),
    # 2026-08-27 fast-viral IssueLink 실응답 누출. 회사 이름만으로 일반 기술·노동
    # 사연을 자르지 않고, 국내 커뮤니티의 종목 별칭 + 시장 행위가 함께 있을 때만 막는다.
    re.compile(
        r"(?:엔비디아|nvidia|sk\s*하이닉스|하이닉스|하닉).{0,24}"
        r"(?:주가|매수|매도|수익|폭등|폭락|급등|급락|상승|하락|올라가|내려가|"
        r"실적|어닝콜|컨퍼런스콜)"
    ),
)

_REAL_ESTATE_CONTEXT_PATTERNS = (
    # "아파트"·"월세" 단독은 층간소음·경비원·집주인 갑질 같은 사연을 통째로 잘라냈다.
    re.compile(r"아파트\s*(?:값|시세|분양|매매|청약|입주권|가격|폭등|폭락)"),
    re.compile(r"월세\s*(?:시세|상승|폭등|수익률|투자)"),
    re.compile(r"(?:집|주택)\s*(?:을|를)?\s*(?:샀|사서|산|팔았|판|매수|매도)"),
    re.compile(r"(?:전세|월세)\s*(?:끼고|계약|보증금|대출|시세)"),
    # 2026-08-27 x-radar 뉴스 랭킹 누출(1,870분 표본): "산 깎아 지은 아파트…또
    # 철렁". 시장 반응 동사가 붙은 아파트 기사만 잡는다 — "아파트서 불"(화재
    # 사연)·"아파트 청소부 실종"은 살아 있어야 한다.
    re.compile(r"아파트.{0,8}(?:철렁|울상|들썩|반등|급등|폭등|폭락)"),
)

_POLITICS_CONTEXT_PATTERNS = (
    re.compile(r"조국\s*(?:혁신당|전\s*장관|대표|사태)"),
    re.compile(r"(?:정부|장관|의원)\s*(?:발표|추진|비판|반박|사퇴|임명|해임|논란|출마)"),
    # 2026-08-27: "독립유공자 모욕 방지법 처리해야"가 통과했다. 법안 계열 명사에
    # '처리·제정' 동사 조합을 더 넓힌다(입법 행위 문맥).
    re.compile(r"(?:법안|정책|방지법|특별법|개정안|기본법)\s*(?:발의|통과|폐기|강행|철회|처리|제정)"),
    re.compile(r"(?:정부|지자체|서울시|경기도|광역시).{0,12}(?:예산|재정|부도|지원금)"),
    # 글로벌 공개 피드를 붙인 뒤 실제 통과한 영어 정치 주제. 단어 경계와 행위 문맥을
    # 함께 써서 ice cream·company president 같은 일상 표현은 삼키지 않는다.
    re.compile(r"\b(?:congress|senate|parliament|supreme court|white house|republicans?|democrats?|prime minister)\b"),
    re.compile(r"\b(?:politics|political|government|attorney general|legislature|senators?|congress(?:man|woman|person)?|lawmakers?)\b"),
    re.compile(r"\b(?:labour|tories|conservative party|republican party|democratic party)(?:'s)?\b"),
    re.compile(r"\b(?:trump|biden|environmental protection agency|epa)\b"),
    re.compile(r"\b(?:election|runoff|ballot|mail voting|campaign trail|trade talks|sanctions)\b"),
    re.compile(r"\bice\s+(?:arrests?|raids?|detention|deportation)\b"),
    re.compile(r"\b(?:russia|ukraine|israel|gaza).{0,24}\b(?:war|strikes?|missiles?|drones?|ceasefire)\b"),
    re.compile(r"\b(?:president|governor|mayor|minister)\b.{0,24}\b(?:election|policy|bill|court|government|campaign|vote|arrest)\b"),
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
    # 2026-08-27 fast-viral 누출: "요즘 여초에서 많이 퍼진다는 기혼녀 혐오 주작".
    # 여초·남초는 성별 진영 어휘로만 쓰인다. "혐오"는 단독으로 넣지 않는다 —
    # (혐오주의) 음식 포스터 같은 컨셉물 대조군이 죽는다.
    "여초",
    "남초",
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
    "오타쿠",
    "덕후짤",
    "성우 캐스팅",
    "신작 애니",
    "애니 추천",
    "애니 명장면",
    "원작 만화",
    "일본 만화",
    "만화 원작",
    # 2026-08-06 화면에서 "요즘 애니회사들…"이 통과했다. "애니" 단독은 애니팡·애니콜과
    # 겹쳐 못 쓰지만, 뒤에 붙는 말이 애니메이션 업계를 가리키면 확정할 수 있다.
    "애니회사",
    "애니업계",
    "애니메",
    "애니 제작",
    "성우진",
    # 2026-08-23 사용자 지시 「레이더에 manhwa도 안 나오게」.
    # **한글 낱말은 하나도 더하지 않았다.** 처음엔 웹툰·만화방·만화카페를 넣었다가
    # test_anime_topics_are_excluded_without_swallowing_lookalikes 가 잡았다 —
    # 2026-08-06 에 «웹툰 작가 지망생이 겪은 갑질» 같은 사연을 잘라낸다는 이유로
    # 일부러 뺀 낱말이었다. 만화방·만화카페도 같은 성질이다(알바·창업 사연이 나온다).
    # 갈라야 할 축은 만화라는 «소재»가 아니라 **소비 검색어인가**이고,
    # 로마자 표기가 그 대리변수다 — 한국어 트렌드에서 manhwa/manga 는 «읽을 것을 찾는»
    # 검색이지 사연이 아니다. 그래서 아래 패턴에만 더한다.
    #   "만화" 단독 → 「만화 같은 역전승」 관용구를 죽인다. 안 넣는다.
    #   "망가"  단독 → 「망가진」·「망가졌다」를 죽인다. 안 넣는다.
    #   "만화가" → 「만화가 아니라」를 죽인다. 안 넣는다.
    # 2026-08-27 x-radar 다음 실시간 트렌드 누출: 웹툰 제목 "재혼황후". 나루토·
    # 귀멸의 칼날처럼 특정 작품명은 일상 낱말과 겹치지 않으므로 제목으로 넣는다.
    "재혼황후",
)

_ANIME_CONTEXT_PATTERNS = (
    re.compile(r"애니\s*(?:방영|공개|1화|\d+화|시즌|캐릭터|주제가|op|ed|명장면|덕후|보는|봤)"),
    re.compile(r"(?:tva|ova|극장판)\s*\d*(?:화|기|기작)?"),
    re.compile(r"(?:작화|성우|나루토|귀칼|귀멸의 칼날|주술회전|체인소맨)\b"),
    # 2026-08-23. 로마자 표기만. 낱말경계로 잡아 mangan(망간) 부분일치를 막는다.
    # webtoon·anime 는 뺐다 — 한글 «웹툰»을 2026-08-06 에 뺀 것과 같은 이유로,
    # 그 낱말이 붙은 노동·갑질 사연이 X 소재로 유효하다.
    re.compile(r"\b(?:manhwa|manhua|manga|donghua|doujin)\b"),
    re.compile(r"\b(?:comic strips?|graphic novels?)\b"),
)


# 핫딜·판촉. 2026-08-06 뽐뿌 HOT을 붙이자 "네이버멤버십 연간 이용권 50프로 할인"이
# 소재로 올라왔다. 커뮤니티에서 반응은 좋지만 X에 옮길 사연이 아니다.
_DEAL_TERMS = (
    "할인", "특가", "최저가", "무료배송", "쿠폰", "적립", "핫딜", "역대가", "품절",
    "공동구매", "공구", "세일", "증정", "이벤트 응모", "기프티콘", "카드할인",
)

_DEAL_PATTERNS = (
    re.compile(r"\d+\s*(?:%|프로|퍼센트)\s*(?:할인|세일|싸)"),
    re.compile(r"(?:원|만원)\s*(?:쿠폰|할인|캐시백)"),
)


def excluded_topic_reason(*values: object) -> str | None:
    """Return the factual exclusion bucket for a topic, if any."""
    haystack = " ".join(str(value or "") for value in values).casefold()
    compact = re.sub(r"\s+", " ", haystack)
    if any(term.casefold() in compact for term in _DEAL_TERMS):
        return "핫딜·판촉 제외"
    if any(pattern.search(compact) for pattern in _DEAL_PATTERNS):
        return "핫딜·판촉 제외"
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
