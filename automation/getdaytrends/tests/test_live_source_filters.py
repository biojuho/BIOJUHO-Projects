"""Tests for factual source expansion and topic exclusions."""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from content_filters import (  # noqa: E402
    _POLITICS_TERMS,
    excluded_topic_reason,
    topic_is_allowed,
)
from dashboard_html import get_dashboard_html  # noqa: E402
from news_origin_collector import parse_bing_news_rss  # noqa: E402


def test_topic_filter_excludes_requested_topics_without_broad_false_positive():
    assert excluded_topic_reason("마요르카 대 PSG") == "스포츠 제외"
    assert excluded_topic_reason("김하성 시즌 20호 홈런") == "스포츠 제외"
    assert excluded_topic_reason("김병지 600만원씩 받고 욕먹은 이유") == "스포츠 제외"
    assert excluded_topic_reason("inter miami vs san luis") == "스포츠 제외"
    assert excluded_topic_reason("이정후 5경기 연속 안타") == "스포츠 제외"
    assert excluded_topic_reason("쇼트트랙 임종언 도핑 징계 위기") == "스포츠 제외"
    assert excluded_topic_reason("롤) 어제 치열한 경기로 1위를 수성한 팀") == "스포츠 제외"
    assert excluded_topic_reason("The NFL Pro Bowl is being eliminated") == "스포츠 제외"
    assert excluded_topic_reason("코스피 장중 급락") == "증시·실적 제외"
    assert excluded_topic_reason("A사 2분기 영업이익 컨센서스 상회") == "증시·실적 제외"
    assert excluded_topic_reason("서울 아파트 실거래가 상승") == "부동산 제외"
    assert excluded_topic_reason("전세 끼고 산 집을 매도했다") == "부동산 제외"
    assert excluded_topic_reason("국회에서 새 법안 통과") == "정치 제외"
    assert excluded_topic_reason("대통령실 개각 검토") == "정치 제외"
    assert excluded_topic_reason("백악관 긴급 브리핑") == "정치 제외"
    assert excluded_topic_reason("트럼프 공화당 행사 참석") == "정치 제외"
    assert excluded_topic_reason("남성연대 신규 영상") == "정치 제외"
    assert excluded_topic_reason("추석 전 민생지원금 또 푼다") == "정치 제외"
    assert excluded_topic_reason("경기도 사실상 부도라네요") == "정치 제외"
    assert topic_is_allowed("제주가 폭염 경보를 발령했다") is True
    assert topic_is_allowed("도심 정전으로 지하철 운행 중단") is True


def test_global_english_politics_are_excluded_without_matching_everyday_ice_or_president():
    assert excluded_topic_reason("ICE arrests hit record high") == "정치 제외"
    assert excluded_topic_reason("Russia-Ukraine war continues") == "정치 제외"
    assert excluded_topic_reason("Supreme Court mail voting case") == "정치 제외"
    assert excluded_topic_reason("SC Senate runoff") == "정치 제외"
    assert excluded_topic_reason("Canada-US trade talks") == "정치 제외"
    assert excluded_topic_reason("Labour's red lines are unmoveable for political reasons") == "정치 제외"
    assert excluded_topic_reason("Attorney general bans a sign in public schools") == "정치 제외"
    assert excluded_topic_reason("Trump's EPA changes data center water rules") == "정치 제외"
    assert topic_is_allowed("Ice cream truck surprises neighborhood kids") is True
    assert topic_is_allowed("Company president gives every employee a bicycle") is True


def test_political_nicknames_are_excluded_even_from_humor_boards():
    """커뮤니티는 정당·정치인을 줄임말과 별칭으로 부른다.

    2026-08-06 보배드림을 붙이자 "국짐이 정청래편인척"이 유머게시판 글로 통과했다.
    게시판 카테고리로는 거를 수 없어(정치 유머가 유머게시판에 올라온다) 표기를 넓혔다.
    """
    assert excluded_topic_reason("국짐이 정청래편인척") == "정치 제외"
    assert excluded_topic_reason("이준석 홍준표 설전 정리") == "정치 제외"
    assert excluded_topic_reason("오세훈 시장 신년 인터뷰") == "정치 제외"
    assert excluded_topic_reason("더불어민주당 새 지도부 구성") == "정치 제외"

    # 애그리게이터 경유로 올라온 글에서도 같은 기준이 걸려야 한다.
    assert excluded_topic_reason("친일파 재산 환수하겠다!") == "정치 제외"
    assert excluded_topic_reason("최민희 발언 정리") == "정치 제외"

    # 일상 화제까지 끌려 들어가면 필터가 무뎌진다.
    assert topic_is_allowed("동네 시장에서 산 붕어빵 후기") is True
    assert topic_is_allowed("국밥집 사장님이 준 서비스") is True


def test_political_roles_institutions_and_actions_are_excluded():
    requested_terms = (
        "선관위",
        "선거관리위원회",
        "시의회",
        "도의회",
        "구의회",
        "군의회",
        "국회의장",
        "상임위",
        "국정감사장",
        "청와대",
        "정부여당",
        "야권",
        "여권",
        "정계",
        "여야",
        "장관",
        "차관",
        "교육감",
        "군수",
        "구청장",
        "국회부의장",
        "당대변인",
        "대변인",
        "의원실",
        "보좌관",
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
    )

    for term in requested_terms:
        assert excluded_topic_reason(f"{term} 관련 소식") == "정치 제외", term

    assert excluded_topic_reason("충격적인 선관위 근황") == "정치 제외"
    assert excluded_topic_reason("당진시의회") == "정치 제외"


def test_politics_expansion_avoids_broad_terms_and_preserves_boundary_verdicts():
    for forbidden_term in ("시장", "대표", "위원장", "후보", "의회"):
        assert forbidden_term not in _POLITICS_TERMS
    assert _POLITICS_TERMS.count("선거") == 1

    # 이 8문장의 변경 전 판정을 그대로 잠근다. 세 문장은 다른 기존 버킷 또는 기존
    # 정치어 "선거"로 이미 제외되므로, 이번 확장이 새 오탐을 만들지 않는지가 게이트다.
    expected_reasons = {
        "동네 재래시장에서 파는 호떡": None,
        "주식시장이 오늘 급락했다": "증시·실적 제외",
        "회사 대표가 회식에서 한 말": None,
        "아파트 입주자대표회의 공지": None,
        "학교 학생회장 선거 후일담": "정치 제외",
        "동호회 회장 뽑는 날": None,
        "드라마 대사가 화제": None,
        "축구 국가대표 발탁": "스포츠 제외",
    }
    for title, expected_reason in expected_reasons.items():
        assert excluded_topic_reason(title) == expected_reason, title


def test_nonpolitical_exclusion_buckets_keep_their_reasons():
    expected_reasons = {
        "프로야구 경기 결과": "스포츠 제외",
        "코스피 장중 급락": "증시·실적 제외",
        "서울 아파트 실거래가 상승": "부동산 제외",
        "남녀 갈등 부추기는 기사": "성별 갈등 제외",
        "신작 애니 추천 좀": "애니·만화 제외",
        "네이버멤버십 이용권 할인": "핫딜·판촉 제외",
    }
    for title, expected_reason in expected_reasons.items():
        assert excluded_topic_reason(title) == expected_reason, title


def test_issuelink_live_leaks_require_a_political_name_or_company_market_context():
    """실제 2026-08-27 IssueLink 누출은 좁게 막고 일반 회사 이야기는 살린다."""
    expected_reasons = {
        "(민형배) ‘모두의 성장‘, 전남광주 반도체로 열겠습니다!": "정치 제외",
        "엔비디아 올라가는 이유.jpg": "증시·실적 제외",
        "오늘 하닉매도하면 7~8월 수익 7억찍을듯?ㅎㅎㅎ": "증시·실적 제외",
        "엔비디아 어닝콜 들어보니 오늘 하닉 폭등각": "증시·실적 제외",
        "엔비디아 일단 실적은 잘나왔고 지금 컨퍼런스콜 중": "증시·실적 제외",
    }
    for title, expected_reason in expected_reasons.items():
        assert excluded_topic_reason(title) == expected_reason, title

    assert topic_is_allowed("엔비디아 AI가 일자리 창출 중이다") is True


def test_dashboard_discloses_keyword_filter_limitations():
    html = get_dashboard_html("0032-test")

    assert html.count("목록에 없는 새 표현은 통과할 수 있습니다.") == 2
    assert html.count("화면에 뜬 것이 곧 안전하다는 뜻은 아닙니다.") == 2
    assert "성인성 제목은 제외합니다" not in html
    assert "애니/만화는 표시하지 않으며" not in html


def test_bing_rss_parser_returns_only_direct_publisher_urls_with_timestamps():
    raw = """<?xml version="1.0" encoding="UTF-8"?>
    <rss xmlns:News="https://example.test/news"><channel>
      <item><title>도심 정전 발생</title>
        <link>http://www.bing.com/news/apiclick.aspx?url=https%3A%2F%2Fnews.example.com%2Fpower%3Fid%3D7</link>
        <pubDate>Wed, 05 Aug 2026 12:05:00 GMT</pubDate><News:Source>Example News</News:Source></item>
      <item><title>스포츠 홈런 소식</title>
        <link>http://www.bing.com/news/apiclick.aspx?url=https%3A%2F%2Fsports.example.com%2F1</link>
        <pubDate>Wed, 05 Aug 2026 12:06:00 GMT</pubDate><News:Source>Sports</News:Source></item>
      <item><title>MSN 재전송</title>
        <link>http://www.bing.com/news/apiclick.aspx?url=https%3A%2F%2Fwww.msn.com%2Farticle</link>
        <pubDate>Wed, 05 Aug 2026 12:07:00 GMT</pubDate><News:Source>Wire on MSN</News:Source></item>
    </channel></rss>""".encode()

    assert parse_bing_news_rss(raw, now=datetime(2026, 8, 5, 13, 0, tzinfo=UTC)) == [
        {
            "title": "도심 정전 발생",
            "url": "https://news.example.com/power?id=7",
            "source": "Example News",
            "published_at": "2026-08-05T12:05:00+00:00",
            "discovered_via": "Bing News RSS",
        }
    ]


def test_gender_conflict_topics_are_excluded():
    """조회·댓글은 잘 나오지만 X로 옮기면 싸움만 남는 소재."""
    assert excluded_topic_reason("패미들 또 시작이네") == "성별 갈등 제외"
    assert excluded_topic_reason("페미니즘 논쟁 정리글") == "성별 갈등 제외"
    assert excluded_topic_reason("남녀 갈등 부추기는 기사") == "성별 갈등 제외"
    assert excluded_topic_reason("이대남 이대녀 표심") == "성별 갈등 제외"

    # "한남"은 지명과 겹친다. 지명까지 걸러 버리면 멀쩡한 글이 사라진다.
    assert topic_is_allowed("한남동 신상 카페 다녀옴") is True
    assert topic_is_allowed("한남대교 야경 사진") is True


def test_anime_topics_are_excluded_without_swallowing_lookalikes():
    assert excluded_topic_reason("극장판 개봉 첫날 후기") == "애니·만화 제외"
    assert excluded_topic_reason("신작 애니 추천 좀") == "애니·만화 제외"
    assert excluded_topic_reason("애니 1화 보는데 작화 미쳤다") == "애니·만화 제외"
    assert excluded_topic_reason("Lemmy · Comic Strips") == "애니·만화 제외"
    # "웹툰"은 2026-08-06에 제외 목록에서 뺐다 — "웹툰 작가 지망생이 겪은 갑질" 같은
    # 사연을 통째로 잘라내고 있었다. 웹툰 화제 자체는 X 소재로 유효하다.
    assert topic_is_allowed("웹툰 작가 지망생이 겪은 갑질") is True


def test_romanized_comic_terms_are_excluded_but_korean_story_words_survive():
    """2026-08-23 사용자 지시 「레이더에 manhwa도 안 나오게」.

    가르는 축은 «만화라는 소재»가 아니라 «소비 검색어인가»다. 로마자 표기가 그
    대리변수다 — 한국어 트렌드에서 manhwa/manga 는 읽을 것을 찾는 검색이지 사연이
    아니다. 반대로 한글 «웹툰»·«만화방»에는 노동·갑질·창업 사연이 붙으므로 살린다.
    (처음 구현에서 웹툰을 다시 넣었다가 위 테스트가 2026-08-06 결정을 되돌리는 것을
    잡아냈다. 그 되돌림을 다시 막기 위해 아래 통과 케이스를 함께 못 박는다.)
    """
    for blocked in ("manhwa 추천 좀", "Manhwa 신작 순위", "manga 번역본",
                    "manhua 사이트", "donghua 추천", "doujin 이벤트"):
        assert excluded_topic_reason(blocked) == "애니·만화 제외", blocked

    for allowed in ("웹툰 작가 지망생이 겪은 갑질", "만화방 알바하다 겪은 일",
                    "만화카페 창업 후기", "망가진 우산 버리는 법",
                    "만화 같은 역전승", "mangan 가격 급등"):
        assert topic_is_allowed(allowed) is True, allowed
    assert excluded_topic_reason("귀멸의 칼날 신작 소식") == "애니·만화 제외"

    # "애니"가 들어가도 애니메이션이 아닌 말들.
    assert topic_is_allowed("애니팡 신기록 세웠다") is True
    assert topic_is_allowed("애니콜 시절 광고 기억나냐") is True


def test_deal_posts_are_excluded_after_adding_ppomppu_hot():
    """뽐뿌 HOT을 붙이자 핫딜이 소재로 올라왔다. 반응은 좋지만 X에 옮길 사연이 아니다."""
    assert excluded_topic_reason("네이버멤버십 연간 이용권 50프로 할인 떴네요") == "핫딜·판촉 제외"
    assert excluded_topic_reason("쿠팡 최저가 특가 정보") == "핫딜·판촉 제외"
    assert excluded_topic_reason("무료배송 쿠폰 뿌립니다") == "핫딜·판촉 제외"

    # 일상 사연에 쓰이는 말까지 끌려가면 안 된다.
    assert topic_is_allowed("할머니가 손주 이벤트에 온 사연") is True
    assert topic_is_allowed("사장이 알바비 떼먹은 이야기") is True


def test_pro_japanese_variants_are_excluded_not_only_compounds():
    """친일파·"친일 청산"만 막고 어간 친일이 누수하면 같은 이슈가 토큰 차이로 통과한다.

    2026-08-14 공급 진단 실측: shadow 10,825건에서 친일이 포함된 행은 allow 119 /
    block 190. 목록에 친일파만 있어 "친일 매국노"·"친일 성향"·"친일청산"(붙여쓰기)이
    전부 통과했다. 친일은 2음절 합성어라 친일파처럼 통째로만 넣으면 변형마다 뚫린다.
    """
    assert excluded_topic_reason("친일 매국노 후손 논란") == "정치 제외"
    assert excluded_topic_reason("친일 성향이 진짜 중에 진짜인 이유") == "정치 제외"
    assert excluded_topic_reason("적극적 친일 가담자 기록도 확인") == "정치 제외"
    assert excluded_topic_reason("친일 인명사전 등재되나") == "정치 제외"
    assert excluded_topic_reason("반민특위 친일청산 실패의 역사") == "정치 제외"

    # 이미 막고 있던 표현은 이번 변경 뒤에도 그대로 막혀야 한다.
    assert excluded_topic_reason("친일파 재산 환수하겠다!") == "정치 제외"
    assert excluded_topic_reason("친일 청산 실패의 역사는 현재진행형") == "정치 제외"
    assert excluded_topic_reason("역사 왜곡 논란 정리") == "정치 제외"

    # 친일이 낱말 경계(공백) 너머에 있는 일상 표현은 끌려 들어가지 않는다.
    assert topic_is_allowed("친구랑 일요일에 간 서점") is True
    assert topic_is_allowed("이사 첫날 무친 일정 탓에 정신없었다") is True


def test_cooking_and_school_contests_are_not_sports():
    """'대회…우승'만으로 스포츠 제외하면 요리·교내 대회 사연이 조용히 사라진다.

    2026-08-07 정답지: "농심배 짜파게티 대회에서 우승한 작품"(X 48만)이 이 패턴에 걸렸다.
    """
    assert topic_is_allowed("농심배 짜파게티 대회에서 우승한 작품") is True
    assert topic_is_allowed("사내 요리 대회에서 우승한 후기") is True
    assert topic_is_allowed("교내 과학 대회 우승 상금 날아간 사연") is True

    # 종목·선수 단서가 있는 대회 우승은 여전히 스포츠다.
    assert excluded_topic_reason("골프 대회에서 우승한 선수 근황") == "스포츠 제외"
    assert excluded_topic_reason("수영 대회 우승 뒤 은퇴 선언") == "스포츠 제외"
    assert excluded_topic_reason("대회 우승 선수 도핑 적발") == "스포츠 제외"
    assert excluded_topic_reason("PGA 투어 우승 상금 공개") == "스포츠 제외"


def test_real_response_leaks_are_blocked_with_exact_reasons():
    """0099 시작 실측 — 실제 /api/x-radar·shadow store allow 판정으로 새어 나온 표본.

    제목 어휘 목록만으로 검사하면 새 표현이 계속 뚫린다. 이 테스트는 2026-08-27
    실응답에서 실제로 통과한 표본을 그대로 못 박는다(누출 근거는 반환 파일 참조).
    """
    blocked = {
        # 증시·기업 실적 — 잭슨홀/연준/통화정책/순익/매출/관세.
        "'통화정책 신호등' 美 잭슨홀 개막…워시 연준의장 첫 시험대": "증시·실적 제외",
        "보험사 상반기 순익 9조 돌파…투자손익 개선 영향": "증시·실적 제외",
        "[만나보니] 엔씨 캐주얼 총괄 \"AI 기반 데이터 분석으로 매출 최적화\"": "증시·실적 제외",
        "엔비디아 2028 매출 70% 증가 전망": "증시·실적 제외",
        "캐나다 주정부, 대미 무역전쟁 동참…美주류에 50% 관세": "정치 제외",  # '주정부'가 정치 어간
        # 스포츠 — 구단·리그명 없이 야구 기록어로만 올라온 KBO 표본과 배드민턴·축구.
        "'0.179 추락 실화?' 삼성, 그래도 만루의 사나이 포기 못 해": "스포츠 제외",
        "삼성 김영웅 만루포": "스포츠 제외",
        "무사만루 찬스에서 끝내기 그랜드슬램": "스포츠 제외",
        "안세영 퍼펙트 우승": "스포츠 제외",
        "'파격 반삭' 홀란, 변신은 '유죄'…역전승에도 침묵": "스포츠 제외",
        "국내 유일 돔구장인데 물이 '또' 샌다…약 30명 대파 소동": "스포츠 제외",
        # 정치 — 정부/대법관 제청/북한/최저임금법/극우 음모론/방지법 처리.
        "정부 AI 윤리원칙": "정치 제외",
        "대법관 2명 동시 제청한 조희대…관례 깬 '서면 통보' 파장": "정치 제외",
        "북한 발사체 발사": "정치 제외",
        "최저임금법": "정치 제외",
        "'샌디훅 사건 날조' 극우 음모론자 배상액 88% 깎아준 美법원": "정치 제외",
        "[백범 탄생 150년] '김구 증손'이 말하는 독립유공자 모욕 방지법 처리해야": "정치 제외",
        # 부동산 — 시장 반응 동사가 붙은 아파트 기사.
        "조선소 들어서자 인구 폭발, 산 깎아 지은 아파트…또 철렁": "부동산 제외",
        # 성별 갈등 — 여초 표현.
        "요즘 여초에서 많이 퍼진다는 기혼녀 혐오 주작": "성별 갈등 제외",
        # 애니·만화 — 웹툰 제목.
        "재혼황후": "애니·만화 제외",
    }
    for title, expected_reason in blocked.items():
        assert excluded_topic_reason(title) == expected_reason, title


def test_real_response_controls_survive_the_leak_expansion():
    """누출 확장의 대조군 — 같은 표면 어휘가 사연에 쓰이면 살아 있어야 한다.

    2026-08-06·08-23 철학 그대로: 블랙리스트는 사연까지 잘라내면 안 된다.
    특히 '아파트서 불'(화재 사건)·'법원'(재판 사연)·'혐오'(컨셉물)은 이번
    확장이 실수로 죽이면 안 되는 경계선이다.
    """
    allowed = (
        # 아파트: 사건·사연 표본 (부동산 시장 기사만 막는다).
        "울산 남구 아파트서 불…4명 연기흡입",
        "MC몽, 손목에 '아파트한 채' 감고 등장",
        "[단독] 장미란씨 없었으면 묻혔을 '아파트 청소부 실종' 전말",
        # 법원: 재판·선고는 유효한 사건 소재 (대법원만 정치로 막는다).
        "'동료 기장 살해' 김동환 무기징역 선고…법원 '영구 격리 필요'",
        # 혐오: 컨셉물 표현 (혐오 진영 어휘만 막는다).
        "(혐오주의) AI로 만든 음식 포스터",
        # 갈등: 새 vs 고양이 (성별 아님).
        "새 지켜야 vs 길냥이도 생명…새파·묘파 갈등",
        # 일상 날씨·전시: 속보가 아니라도 최신 뉴스 lane의 유효 소재.
        "제주 해안 전역 또 열대야…성산 최저 28.5도",
        "수어로 빚은 마음부터…갤러리현대 두 전시",
        # 매출/만루 등 확장 어휘가 없는 일상 사연 대조군.
        "동네 재래시장에서 파는 호떡",
        "호텔가, 추석선물 경쟁…와인세트 인기",
    )
    for title in allowed:
        assert topic_is_allowed(title) is True, title
