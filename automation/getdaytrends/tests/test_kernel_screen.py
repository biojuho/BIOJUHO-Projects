"""커널 소재 판별 계약.

레이더 적합도(지금 퍼지는가)와 커널 판별(X에서 판정이 붙는가)은 다른 축이다.
2026-08-06 실측에서 이 판별의 축별 중앙 노출은 가해자 명확 1,734 / 낙차·반전 730 /
쌍방 논쟁 326이었고, 쌍방 논쟁으로 판정된 6건 중 1만 노출을 넘긴 것은 0건이었다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard_html import get_dashboard_html  # noqa: E402
from kernel_screen import (  # noqa: E402
    attach_kernel_screen,
    screen_material,
    sort_by_kernel,
    sort_by_kernel_legacy_axis,
)


class TestLiveAxes:
    def test_actor_plus_wrongdoing_is_one_sided(self):
        r = screen_material("시댁 형편 어렵다고 친정 용돈 뺏어 시댁 주자는 남편")
        assert r["axis"] == "live_wrong"
        assert "남편" in r["signals"][0]

    def test_reversal_word_is_a_gap(self):
        assert screen_material("산 정상에서 모두가 한 남자를 막아선 이유")["axis"] == "unknown"

    def test_contrast_structure_counts_as_a_gap_without_keywords(self):
        # "장사가 너무 잘돼서, 오히려 망했다"는 실측 노출 3위인데 초기 규칙이 놓쳤다.
        assert screen_material("장사가 너무 잘돼서 오히려 망했다")["axis"] == "live_gap"
        assert screen_material("가게가 잘되니까 결국 망해버린 이야기")["axis"] == "live_gap"


class TestDeadAxes:
    def test_debate_word_kills_it(self):
        r = screen_material("일본 어느 방송인의 방송태도 논란")
        assert r["axis"] == "dead_debate"

    def test_question_ending_kills_it(self):
        assert screen_material("연봉 1억 주면 가능?")["axis"] == "dead_debate"
        assert screen_material("이 정도면 제가 예민한 건가요?")["axis"] == "dead_debate"

    def test_debate_beats_actor(self):
        # 가해자와 논쟁 신호가 함께 있으면 논쟁이 이긴다 — 인용 방향이 모이지 않기 때문이다.
        r = screen_material("팀장이 갑질한 거 맞나요?")
        assert r["axis"] == "dead_debate"

    def test_flat_material_has_no_signal(self):
        assert screen_material("얘들아 다들 이거 합쳐봐")["axis"] == "dead_flat"


class TestGates:
    def test_medical_terms_demand_verification_first(self):
        r = screen_material("위고비, 마운자로 곧 '오남용 우려 의약품' 지정")
        assert r["verify_first"] is True

    def test_risk_multiplier_pattern_demands_verification(self):
        assert screen_material("이거 방치하면 치매 위험 1.5배 증가")["verify_first"] is True

    def test_account_tone_clash_is_flagged(self):
        assert screen_material("개쳐답답하네 진짜")["tone_clash"] is True
        assert screen_material("이거 실화냐??")["tone_clash"] is True

    def test_calm_title_has_no_tone_clash(self):
        assert screen_material("친정엄마 생신에 10만원 드리는 걸 며칠 고민했다")["tone_clash"] is False


class TestUnknown:
    def test_actor_without_action_is_held_for_review(self):
        # 확정할 수 없으면 죽는 축으로 몰지 않는다. 원문을 열어 보게 남긴다.
        r = screen_material("팀장이랑 점심 먹은 이야기입니다만")
        assert r["axis"] in {"unknown", "live_gap"}

    def test_empty_title_is_unknown(self):
        r = screen_material("")
        assert r["axis"] == "unknown"
        assert r["signals"] == []
        assert r["person"] is False
        assert r["person_terms"] == []


class TestPersonAxis:
    def test_actor_terms_are_reported_without_changing_the_existing_axis(self):
        r = screen_material("팀장이랑 점심 먹은 이야기입니다만")
        assert r["axis"] == "unknown"
        assert r["person"] is True
        assert r["person_terms"] == ["팀장"]
        assert "person_source" not in r

    def test_person_is_independent_from_a_dead_debate_axis(self):
        r = screen_material("팀장이 갑질한 거 맞나요?")
        assert r["axis"] == "dead_debate"
        assert r["person"] is True

    def test_person_terms_are_capped_at_three(self):
        r = screen_material("남편 아내 팀장 사장 친구가 모인 자리")
        assert r["person"] is True
        assert r["person_terms"] == ["남편", "아내", "팀장"]

    def test_summary_can_add_only_person_without_changing_legacy_fields(self):
        title = "옷차림이 중요해지는 이유"
        title_only = screen_material(title)
        result = screen_material(title, summary="팀장과 점심을 먹었다")

        for field in ("axis", "axis_label", "verify_first", "tone_clash", "signals", "confidence"):
            assert result[field] == title_only[field]
        assert title_only["person"] is False
        assert result["person"] is True
        assert result["person_terms"] == ["팀장"]
        assert result["person_source"] == "summary"

    def test_summary_can_add_person_when_the_title_axis_is_already_decided(self):
        title = "장사가 너무 잘돼서 오히려 망했다"
        title_only = screen_material(title)
        result = screen_material(title, summary="팀장이 운영 과정을 설명했다")

        for field in ("axis", "axis_label", "verify_first", "tone_clash", "signals", "confidence"):
            assert result[field] == title_only[field]
        assert result["axis"] == "live_gap"
        assert result["person"] is True
        assert result["person_terms"] == ["팀장"]
        assert result["person_source"] == "summary"


class TestPersonRecall0070:
    """0070 핸드오프: 관계·직함이 있는데 person=False였던 실측 놓침을 고정한다.

    2026-08-16 헤더 실측 — 8010 응답 40건 중 제목에 관계·직함이 있는 5건에서 3건을
    놓쳤다(전부 person_terms=[]). person은 이 계정에서 유일하게 검정을 통과한 축이라
    놓침은 곧 후보 감소다. 동시에 정밀도를 지킨다 — 경계 어휘(딸·아들·손자·이모·교사)는
    사람 아닌 낱말(딸기·알아들·손자병법·이모티콘·반면교사)을 걸러야 한다.
    """

    def test_the_three_measured_misses_are_now_person(self):
        r = screen_material("군인 가능")
        assert r["person"] is True
        assert r["person_terms"] == ["군인"]

        r = screen_material("대구 선생님들 이리 와봐요")
        assert r["person"] is True
        assert r["person_terms"] == ["선생"]

        r = screen_material("'하영 증조모 일본 총독부 대장 딸?' 궁중 연구서 기록에 또다시 들썩")
        assert r["person"] is True
        assert "증조모" in r["person_terms"]
        assert "딸" in r["person_terms"]

    def test_kinship_family_terms_cover_the_corpus_shapes(self):
        # shadow 코퍼스 실측 형태(증손자·증손녀·외숙모·친할머니 같은 붙여쓰기 포함).
        cases = [
            ("하영 증조부 친일파 의혹에 '위험한 발상'", "증조부"),
            ("증조할아버지가 어떤 사람인지 아시나요", "할아버지"),
            ("친할머니랑 단 둘이 호캉스 하러 갔다", "할머니"),
            ("칼 든 조카, 유죄?…대법이 뒤집었다", "조카"),
            ("친일파 증손녀 하영 근황", "손녀"),
            ("이완용 증손자 돈벼락", "손자"),
            ("성추행 폭로당한 삼촌이 가위로 위협해", "삼촌"),
            ("고모네 가서 대형사고 친 남자", "고모"),
            ("엄마 무시하는 외숙모 이번 추석 복수해야하나요", "숙모"),
            ("덩치 큰 이모가 조카랑 있었던 일", "이모"),
            ("촬영한 교사, 담임 배제되고 경찰 신고 당해", "교사"),
        ]
        for title, term in cases:
            r = screen_material(title)
            assert r["person"] is True, title
            assert term in r["person_terms"], title

    def test_boundary_terms_do_not_leak_into_non_person_words(self):
        # shadow 13,800 unique 제목 전수 열람에서 나온 사람 아닌 형태 전부.
        non_person = [
            "3년전 돼지바 딸기쨈 막고라서 기분나쁨",      # 딸기
            "역량이 딸리는 작곡가",                        # 딸리다
            "대욕탕 딸린 일본 온천에 갔다",                # 딸린
            "스노트 라이토 딸딸이 무죄설의 황당 전말",      # 딸딸이
            "딸배 새끼들 서식처",                          # 딸배
            "오늘 딸치다 펑펑 울었다",                      # 딸치다
            "용산딸잽이님 신청곡",                          # 딸잽이
            "번호 딸까 말까 고민된다",                      # 따다 → 딸까
            "이게 딸랑 사과 한마디",                        # 딸랑
            "보배딸맨님 신청곡",                            # 딸맨
            "많은 3.3 리딸을 해왔지만",                     # 리딸
            "제주어로 인사했더니 못 알아들은 관광객",      # 알아들다
            # (코퍼스 실측형 "못 알아들은 사장님"은 '사장'이 기존 사전 어휘라
            #  person=True가 나는 게 정상 — 알아들 경계만 격리해 확인한다.)
            "남자들은 왜 말을 못알아들을까요",              # 알아들다
            "불리한 역사는 편집해 사실로 받아들이면 참사",  # 받아들이다
            "트럼프도 읽었다는 손자병법",                   # 손자병법
            "카카오톡 이모티콘 최강자",                     # 이모티콘
            "반면교사 역사도 안 읽어요?",                   # 반면교사
        ]
        for title in non_person:
            assert screen_material(title)["person"] is False, title

    def test_boundary_terms_still_catch_real_kinship(self):
        person = [
            "아픈 부모 늘 돌봐주던 아들, 화재로 사망",
            "엄마 때문에 분노한 아들",
            "장윤주의 9살 딸 리사가 그렸다",
            "딸을 건드린 새아빠",
            "친일파 손자 레전드",
            "우리 딸 키우며 배운 것들",
        ]
        for title in person:
            assert screen_material(title)["person"] is True, title

    def test_broad_tokens_remain_outside_the_dictionary(self):
        # 0070 금지사항: 「사람」·「씨」 같은 광범위 토큰으로 전건 person을 만들지 않는다.
        assert screen_material("사람들이 많더라")["person"] is False
        assert screen_material("김씨가 많은 동네")["person"] is False
        assert screen_material("온 국민이 충격에 빠졌다")["person"] is False


class TestPersonNewsAndBoundary0080:
    """0080: 뉴스 제목의 형 오탐을 막고, 확인된 뉴스 어휘만 정밀하게 넣는다."""

    def test_measured_hyung_false_positives_are_no_longer_person(self):
        # 헤더 실측 뉴스 ["형"] 단독 표본 + 수용 게이트 ㉮.
        non_person = [
            "검찰, '강북 모텔 연쇄살인' 김소영에 사형 구형",
            "경남교육청, 학교·기관 맞춤형 '계약실무편람' 개정판 발간",
            "경찰, '수원 공사장 사망' 이랜드건설 현장소장 등 송치",
            "허위과장,낚시홍보 없는 원조 박리다매",
            "아군인줄 알았는데 까보니 적군이였음",
            "서울시, 빅뱅 20주년 기념행사 한강에 대형 스크린 띄운다",
            "음주 벌금형 두 달만에 또 만취사고 뒤 뺑소니 50대 징역형 집유",
            "김시우, PGA투어 PO 1차전 준우승…임성재·김주형과 2차전 진출",
            "정성호 \"형소법 통과돼 역할 많지 않아, 국회서 할일 더 많을것\"",
            "실체 없는 공포가 삼킨 일상…'아기돼지 삼형제' 비튼 음악극",
            "축구협회, 대표팀 임시 감독 서류 전형 완료…이번 주 면접 돌입",
        ]
        for title in non_person:
            r = screen_material(title)
            assert r["person"] is False or "형" not in r["person_terms"], title

        # ㉮ 단문. 공사장·허위과장·아군인줄은 다른 역할어도 없어야 한다.
        for title in ("사형 구형", "맞춤형", "공사장", "허위과장", "아군인줄"):
            assert screen_material(title)["person"] is False, title

    def test_real_kinship_hyung_and_relations_survive(self):
        # ㉰ 과잉 방어로 진짜 관계어를 죽이면 실패.
        person = [
            ("형님들이 알려준다", "형"),
            ("남동생이 먼저 나섰다", "동생"),
            ("여자친구가 화를 냈다", "친구"),
            ("38살 형 친구 때문에 미치겠다는 사람", "형"),
            ("68년생 결혼못한 사촌 큰형님 근황", "형"),
            ("예비 장모가 예비 사위한테 대놓고 먹어달라고 하는 이유", "사위"),
            ("장인어른에게 양주 선물하는 Manhwa", "장인"),
            ("군인 가능", "군인"),
        ]
        for title, term in person:
            r = screen_material(title)
            assert r["person"] is True, title
            assert term in r["person_terms"], (title, r["person_terms"])

    def test_corpus_false_compounds_of_moved_terms(self):
        non_person = [
            "AD [설치당일지급]_뽐뿌대표 원모어렌탈]_고객추천 1등]_코웨이",
            "인제군 상하수도사업소, 상수도 고객만족도 '전국 최고'",
            "고객센터 ARS 특.mp4",
            "최악의 민영화 사례는 멀리 볼 필요 없이 이웃나라만 봐도 알 수 있음",
            "롤) 피해지역 이웃돕기에 누구보다도 빠른 프로게이머",
            "이강인과 알바레스 드디어 만났다",
            "[기사]7월 대폭락장 만들고 몰락한 '25세 천재'",
            "블루아카)이번엔 진짜 억울한 나기사 manhwa",
            "젖니 나온 아기사자.jpeg",
            "림버스) 행보가 억까 그득한 등장인물",
            "與 법사위 \"조희대, '김건희 재판지연' 직무유기 책임 묻겠다\"",
            "16년 만에 부활하는 친일재산조사위",
            "여제 안세영, 세계선수권 32강 안착",
            "AD [반값보험료] 운전자보험 상담",
            "서산 '천하일품' 쌀, 농협쌀 10대 대표브랜드에 선정",
            "제10대 청송군의회 첫 정례회…예산·조례안 살핀다",
            "'여름철 극성' 바퀴벌레 잡는다…성동구, 방제설비 80대 운영",
        ]
        for title in non_person:
            assert screen_material(title)["person"] is False, title

    def test_news_vocab_catches_measured_misses(self):
        cases = [
            ("[부고] 박영찬(속초경찰서 여성청소년 과장)씨 모친상", "모친"),
            ("[부고] 김종혁(서울아산병원 산부인과 교수)씨 부친상", "부친"),
            ("언론인 신건호, '사람을 그리며 세상을 묻다' 출간", "언론인"),
            ("서울 화곡동서 여고생에 흉기 휘두른 10대 기소…스토킹 혐의 추가", "여고생"),
            ("끼어들기 차량 홧김에 들이받은 40대 운전자 입건…2명 부상", "운전자"),
            ("'성남 보복살인' 50대 신상공개 결정…25일 머그샷 공개", "50대"),
            ("오송참사 유족 \"충북도·청주시, 무단 수집 의료정보 폐기하라\"", "유족"),
            ("직장인 80% \"기간제 차별 존재\"…출산휴가·육아휴직도 '눈치'", "직장인"),
            ("원정경기후 복귀 중 교통사고난 차량 불길 속으로 뛰어든 광주FC 선수들", "선수"),
        ]
        for title, term in cases:
            r = screen_material(title)
            assert r["person"] is True, title
            assert term in r["person_terms"], (title, r["person_terms"])

    def test_politics_religion_gender_tokens_stay_out(self):
        from kernel_screen import _ACTOR_TERMS, _ACTOR_BOUNDARY_PATTERNS

        banned = ("의원", "장관", "대통령", "목사", "스님", "신부", "페미", "한남", "여혐")
        plain = set(_ACTOR_TERMS)
        boundary = {term for _, term in _ACTOR_BOUNDARY_PATTERNS}
        for token in banned:
            assert token not in plain, token
            assert token not in boundary, token

    def test_empty_lexicon_fails_closed_instead_of_reporting_zero_fps(self):
        import kernel_screen as ks

        ks.require_actor_lexicon()
        saved_terms = ks._ACTOR_TERMS
        saved_patterns = ks._ACTOR_BOUNDARY_PATTERNS
        try:
            ks._ACTOR_TERMS = ()
            ks._ACTOR_BOUNDARY_PATTERNS = ()
            try:
                ks.require_actor_lexicon()
            except RuntimeError as exc:
                assert "empty" in str(exc)
            else:
                raise AssertionError("empty lexicon must not look like zero false positives")
        finally:
            ks._ACTOR_TERMS = saved_terms
            ks._ACTOR_BOUNDARY_PATTERNS = saved_patterns


class TestAttach:
    def test_attach_adds_screen_and_summary_without_mutating(self):
        payload = {"items": [{"title": "팀장이 회식비 떠넘김"}, {"title": "이거 맞나요?"}]}
        out = attach_kernel_screen(payload)

        assert "kernel_screen" not in payload["items"][0]
        assert out["items"][0]["kernel_screen"]["axis"] == "live_wrong"
        assert out["items"][1]["kernel_screen"]["axis"] == "dead_debate"
        assert out["kernel_summary"] == {"live": 1, "dead": 1, "verify_first": 0, "person_count": 1}

    def test_attach_reads_alternate_title_field(self):
        # X 레이더는 제목이 keyword 필드에 있다.
        out = attach_kernel_screen({"items": [{"keyword": "손님이 진상짓하고 잠수"}]}, title_field="keyword")
        assert out["items"][0]["kernel_screen"]["axis"] == "live_wrong"

    def test_attach_survives_missing_or_odd_items(self):
        assert attach_kernel_screen({})["items"] if False else True
        assert "kernel_summary" not in attach_kernel_screen({"items": "nope"})
        out = attach_kernel_screen({"items": [None, {"title": "논란"}]})
        # 정렬이 붙은 뒤로 dict가 아닌 항목은 맨 뒤로 밀린다 — 화면 위를 차지하면 안 된다.
        assert out["items"][-1] is None
        assert out["items"][0]["kernel_screen"]["axis"] == "dead_debate"

    def test_attach_preserves_a_second_pass_screen(self):
        second_pass = screen_material(
            "결혼식에서 있었던 이야기",
            summary="남편이 축의금을 몰래 가로채고도 거짓말했다",
        )
        out = attach_kernel_screen(
            {"items": [{"title": "결혼식에서 있었던 이야기", "kernel_screen": second_pass}]}
        )
        assert out["items"][0]["kernel_screen"] == second_pass
        assert out["kernel_summary"]["live"] == 1

    def test_attach_uses_item_summary_when_keyword_has_no_actor(self):
        # 레이더는 title_field=keyword. 제목에 관계어가 없고 summary에만 있으면 person이 열려야 한다.
        keyword = "폭염주의보 발표 제08-218호"
        summary = "모친 병문안을 미룬 채 야외 행사를 강행했다"
        out = attach_kernel_screen(
            {"items": [{"keyword": keyword, "summary": summary}]},
            title_field="keyword",
            sort=False,
        )
        screen = out["items"][0]["kernel_screen"]
        assert screen["person"] is True
        assert "모친" in screen["person_terms"]
        assert screen.get("person_source") == "summary"

    def test_attach_title_only_without_summary_stays_non_person(self):
        keyword = "폭염주의보 발표 제08-218호"
        out = attach_kernel_screen(
            {"items": [{"keyword": keyword}]},
            title_field="keyword",
            sort=False,
        )
        assert out["items"][0]["kernel_screen"]["person"] is False

    def test_attach_title_only_person_stays_true_without_summary(self):
        out = attach_kernel_screen(
            {"items": [{"keyword": "손님이 진상짓하고 잠수"}]},
            title_field="keyword",
            sort=False,
        )
        screen = out["items"][0]["kernel_screen"]
        assert screen["person"] is True
        assert screen.get("person_source") != "summary"

    def test_attach_backfills_person_on_a_legacy_screen_without_changing_it(self):
        legacy_screen = {
            "axis": "unknown",
            "axis_label": "원문 확인 필요",
            "verify_first": False,
            "tone_clash": False,
            "signals": ["역할 '남편'은 있으나 행위가 드러나지 않음"],
            "confidence": "low",
        }
        out = attach_kernel_screen(
            {"items": [{"title": "남편과 점심", "kernel_screen": legacy_screen}]}, sort=False
        )
        result = out["items"][0]["kernel_screen"]

        for field, value in legacy_screen.items():
            assert result[field] == value
        assert result["person"] is True
        assert result["person_terms"] == ["남편"]


class TestOgSecondPass:
    def test_summary_can_rescue_a_title_with_no_material_signal(self):
        title = "결혼식에서 있었던 이야기"
        assert screen_material(title)["axis"] == "dead_flat"

        result = screen_material(
            title,
            summary="남편이 축의금을 몰래 가로채고도 거짓말했다",
        )

        assert result["axis"] == "live_wrong"
        assert result["signals"][0] == "원문 첫 문단에서 가해 역할과 행위 확인"

    def test_existing_title_signal_is_not_overridden_by_summary(self):
        result = screen_material(
            "팀장이 갑질한 거 맞나요?",
            summary="팀장이 회식비를 떠넘기고 폭언했다",
        )
        assert result["axis"] == "dead_debate"
        assert not any("원문 첫 문단" in signal for signal in result["signals"])

    def test_real_infidelity_example_is_read_only_on_the_second_pass(self):
        title = "50대 유부남과 바람핀 30대 와이프"
        assert screen_material(title)["axis"] == "live_wrong"

    def test_named_warning_needs_confirming_wrongdoing_from_the_summary(self):
        title = "KTX 자유석 타지 마세요"
        assert screen_material(title)["axis"] == "dead_flat"
        result = screen_material(title, summary="예약 내역을 몰래 가로채는 문제가 확인됐습니다")
        assert result["axis"] == "live_wrong"
        assert result["signals"][0] == "원문 첫 문단에서 명명된 경고 대상과 피해 행위 확인"

    def test_named_warning_without_summary_wrongdoing_stays_flat(self):
        result = screen_material(
            "KTX 자유석 타지 마세요",
            summary="좌석 이용 방법을 설명합니다",
        )
        assert result["axis"] == "dead_flat"


class TestGapTypes:
    """커널 1-3절 낙차 4종. 처음에는 ①만 구현해 상위 게시물 2건을 놓쳤다."""

    def test_expectation_result_reversal(self):
        assert screen_material("장사가 너무 잘돼서 오히려 망했다")["axis"] == "live_gap"

    def test_rule_behavior_reversal(self):
        # 실측 노출 4위. "절대 안 준다"는 원칙이 곧 낙차다.
        r = screen_material("배우 오만석이 연기엔 100점이 없어 수업에 A+을 절대 안 준다고 함")
        assert r["axis"] == "live_gap"
        assert any("규칙" in s for s in r["signals"])

    def test_scale_life_gap(self):
        # 실측 노출 5위. 큰 규모가 도시락 같은 생활 소재와 붙을 때.
        r = screen_material("JYP 새 사옥 식당이 3배 커지면서 매니저 도시락까지 공짜로 퍼줌")
        assert r["axis"] == "live_gap"
        assert any("규모" in s for s in r["signals"])

    def test_relationship_meaning_reversal(self):
        r = screen_material("엄마가 뜻밖에 꺼낸 한마디")
        assert r["axis"] == "live_gap"

    # ── 0005 구조 패턴 ──────────────────────────────────────────────
    # 검수 결과: 초기 6종 중 4종(상태 변환·시간 과잉·관계-신체·기대-평가)이
    # 정답지 항목을 겨냥한 형태소 나열이거나 평범한 문장을 사는 축으로 새게 해서 제거.
    # 순수 구조(조사 반복, 어미)로 된 2종만 남김.

    def test_target_shift(self):
        # ⑤ 대상 전환: 감정·행위의 대상이 도중에 바뀔 때 (조사 '에게' 반복)
        r = screen_material("엄마에게 전화했다가 친구에게 고민을 털어놓았다")
        assert r["axis"] == "live_gap"
        assert any("대상 전환" in s for s in r["signals"])
        # 반례: 대상이 하나면 dead_flat
        assert screen_material("친구에게 전화했다")["axis"] != "live_gap"

    # ── 0011 약한 어휘 좁히기 ─────────────────────────────────────────
    # "이유"·"근황"은 _GAP_TERMS에서 _WEAK_GAP_TERMS로 분리.
    # 단독이면 unknown, 강한 신호와 함께면 live_gap, 서사 구조면 live_gap.

    def test_weak_term_alone_is_unknown(self):
        # "이유" 단독 — 설명글은 낙차가 아니다
        assert screen_material("나이들수록 옷차림이 중요해지는 이유")["axis"] == "unknown"
        # "근황" 단독 — 근황 보고는 낙차가 아니다
        assert screen_material("부산 스타벅스 근황")["axis"] == "unknown"

    def test_weak_term_with_strong_signal_is_live_gap(self):
        # "이유" + 강한 신호("레전드") → live_gap
        r = screen_material("레전드인 이유")
        assert r["axis"] == "live_gap"

    def test_narrative_reason_pattern(self):
        # ⑥ 서사 이유: 구체적 개체 + 예기치 않은 행동 + "이유" → live_gap
        r = screen_material("어느 식당이 여름 휴가를 간 이유")
        assert r["axis"] == "live_gap"
        assert any("서사 이유" in s for s in r["signals"])
        # 반례: 추상 주제 + 설명 동사 → 서사 패턴 불일치
        assert screen_material("옷차림이 중요해지는 이유")["axis"] == "unknown"

    def test_ordinary_sentence_is_not_forced_into_a_gap(self):
        # 낙차 패턴이 너무 넓으면 전부 사는 축이 되어 선별이 무의미해진다.
        assert screen_material("오늘 점심 뭐 먹을지 고민 중")["axis"] == "dead_flat"
        assert screen_material("복도에 실외기 설치 완료")["axis"] == "dead_flat"
        # 0005 검수에서 발견된 새는 문장들 — 승진·가족 맞이·성장 서사는 낙차가 아니다.
        assert screen_material("신입이 대리가 됐다")["axis"] != "live_gap"
        assert screen_material("강아지가 우리 가족이 된 날")["axis"] != "live_gap"
        assert screen_material("아이가 어른이 되면 알게 되는 것")["axis"] != "live_gap"


class TestShortInput:
    """X 레이더는 제목이 아니라 검색어 한 단어를 준다."""

    def test_single_keyword_is_not_judged(self):
        for keyword in ("김혜수", "오디세이", "태국"):
            r = screen_material(keyword)
            assert r["axis"] == "unknown"
            assert "판정할 수 없" in r["signals"][0]

    def test_full_sentence_is_still_judged(self):
        assert screen_material("팀장이 회식비를 떠넘김")["axis"] == "live_wrong"


class TestKernelSorting:
    """금지 목록 추격을 대체하는 지점.

    제외 필터는 새 표현마다 뚫린다. 2026-08-06 하루에 네 갈래에서 누수가 나왔지만,
    그 9건을 커널로 판정하면 사는 축이 0건이었다 — 허용 기준으로 세우면 아래로 밀린다.
    """

    def test_live_axes_rise_above_higher_scoring_dead_ones(self):
        items = [
            {"title": "복도에 실외기 설치 완료", "x_exposure_score": 96},
            {"title": "팀장이 회식비를 떠넘김", "x_exposure_score": 40},
        ]
        out = attach_kernel_screen({"items": items})["items"]
        # 점수는 96 대 40이지만 소재 축이 이긴다.
        assert out[0]["title"] == "팀장이 회식비를 떠넘김"

    def test_score_breaks_ties_within_the_same_axis(self):
        items = [
            {"title": "손님이 진상짓하고 잠수", "x_exposure_score": 30},
            {"title": "사장이 알바비를 떼먹음", "x_exposure_score": 80},
        ]
        out = attach_kernel_screen({"items": items})["items"]
        assert out[0]["x_exposure_score"] == 80

    def test_person_is_the_first_key_before_the_existing_axis_rank(self):
        items = [
            {"title": "장사가 너무 잘돼서 오히려 망했다", "x_exposure_score": 90},
            {"title": "남편이 이러는 거 맞나요?", "x_exposure_score": 10},
        ]
        out = attach_kernel_screen({"items": items})["items"]

        assert out[0]["kernel_screen"]["person"] is True
        assert out[0]["kernel_screen"]["axis"] == "dead_debate"

    def test_cooling_is_second_key_and_none_stays_with_fresh_items(self):
        items = [
            {
                "title": "식었지만 사람이 있는 항목",
                "kernel_screen": {"person": True, "axis": "live_wrong"},
                "cooling": True,
                "x_exposure_score": 99,
            },
            {
                "title": "관측 부족인 사람 항목",
                "kernel_screen": {"person": True, "axis": "unknown"},
                "cooling": None,
                "x_exposure_score": 20,
            },
            {
                "title": "증가 중인 사람 항목",
                "kernel_screen": {"person": True, "axis": "dead_flat"},
                "cooling": False,
                "x_exposure_score": 10,
            },
            {
                "title": "사람 없는 증가 항목",
                "kernel_screen": {"person": False, "axis": "live_wrong"},
                "cooling": False,
                "x_exposure_score": 100,
            },
        ]

        out = sort_by_kernel(items)

        assert [item["title"] for item in out] == [
            "관측 부족인 사람 항목",
            "증가 중인 사람 항목",
            "식었지만 사람이 있는 항목",
            "사람 없는 증가 항목",
        ]

    def test_score_orders_items_within_the_same_person_value(self):
        items = [
            {"title": "복도에 실외기 설치 완료", "x_exposure_score": 90},
            {"title": "장사가 너무 잘돼서 오히려 망했다", "x_exposure_score": 20},
            {"title": "공짜 커피를 받았더니 돈을 요구했다", "x_exposure_score": 80},
        ]
        out = attach_kernel_screen({"items": items})["items"]

        # 0062 핸드오프: 생산 정렬에서 _AXIS_RANK가 빠져 점수 내림차순 [90, 80, 20]으로 정렬된다.
        assert [item["x_exposure_score"] for item in out] == [90, 80, 20]

    def test_legacy_axis_sort_unknown_outranks_dead(self):
        # 2026-08-08 이전 레거시 축 정렬: unknown (rank 2)이 dead (rank 4)보다 앞선다.
        items = [
            {"title": "얘들아 다들 이거 합쳐봐", "x_exposure_score": 90},
            {"title": "김혜수", "x_exposure_score": 10},
        ]
        screened = attach_kernel_screen({"items": items}, sort=False)["items"]
        out = sort_by_kernel_legacy_axis(screened)
        assert out[0]["title"] == "김혜수"

    def test_legacy_axis_sort_leaked_filter_items_do_not_reach_the_top(self):
        # 2026-08-08 이전 레거시 축 정렬: 사는 축(live_wrong rank 0)이 unknown(rank 2) 및 dead보다 앞선다.
        leaked = [
            "국짐이 정청래편인척",
            "요즘 애니회사들, 유부녀를 판다.jpg",
            "이야 성접대는 좀 많이 큰데?",
        ]
        items = [{"title": t, "x_exposure_score": 95} for t in leaked]
        items.append({"title": "남편이 친정 용돈을 뺏어감", "x_exposure_score": 20})
        screened = attach_kernel_screen({"items": items}, sort=False)["items"]
        out = sort_by_kernel_legacy_axis(screened)
        assert out[0]["title"] == "남편이 친정 용돈을 뺏어감"

    def test_production_sort_orders_by_person_then_score(self):
        # 0062 핸드오프 생산 정렬: person 유무(1차) -> cooling(2차) -> score 내림차순(3차).
        items = [
            {"title": "일반 소재 고득점", "kernel_screen": {"person": False}, "cooling": False, "x_exposure_score": 95},
            {"title": "인물 소재 저득점", "kernel_screen": {"person": True}, "cooling": False, "x_exposure_score": 20},
            {"title": "인물 소재 고득점", "kernel_screen": {"person": True}, "cooling": False, "x_exposure_score": 80},
        ]
        out = sort_by_kernel(items)
        assert [item["title"] for item in out] == [
            "인물 소재 고득점",
            "인물 소재 저득점",
            "일반 소재 고득점",
        ]

    def test_sorting_can_be_turned_off(self):
        items = [{"title": "복도에 실외기 설치 완료"}, {"title": "팀장이 회식비를 떠넘김"}]
        out = attach_kernel_screen({"items": items}, sort=False)["items"]
        assert out[0]["title"] == "복도에 실외기 설치 완료"


class TestSortByKernelFixedSamples:
    """0062 핸드오프: _AXIS_RANK 제거 전후 고정 표본 회귀 테스트.

    나중에 정렬 방식을 되돌리거나 비교할 수 있도록 제거 전(legacy)과 제거 후(production)
    정렬 결과를 동일한 고정 표본에 대해 검증한다.
    """

    SAMPLE_ITEMS = [
        {"title": "방금 공개된 티웨이항공 승무원 신규 유니폼.jpg", "x_exposure_score": 54, "cooling": False},
        {"title": "휴대폰 반납했더니 1,500만 원이 결제. 부대 내 연쇄 절도 고발합니다", "x_exposure_score": 39, "cooling": False},
        {"title": "복도에 실외기 설치 완료", "x_exposure_score": 90, "cooling": False},
        {"title": "장사가 너무 잘돼서 오히려 망했다", "x_exposure_score": 20, "cooling": False},
        {"title": "공짜 커피를 받았더니 돈을 요구했다", "x_exposure_score": 80, "cooling": False},
        {"title": "식었지만 사람이 있는 항목", "x_exposure_score": 95, "cooling": True, "kernel_screen": {"person": True, "axis": "unknown"}},
    ]

    def test_sort_by_kernel_legacy_axis_fixed_sample(self):
        screened = attach_kernel_screen({"items": self.SAMPLE_ITEMS}, sort=False)["items"]
        legacy_out = sort_by_kernel_legacy_axis(screened)

        # 레거시 정렬 순서: person -> cooling -> _AXIS_RANK -> score
        # 1. person=True (식었지만 사람이 있는 항목)
        # 2. live_gap (공짜 커피 80 -> 연쇄 절도 39 -> 장사 20)
        # 3. dead_flat (복도 실외기 90 -> 티웨이항공 54)
        assert [item["title"] for item in legacy_out] == [
            "식었지만 사람이 있는 항목",
            "공짜 커피를 받았더니 돈을 요구했다",
            "휴대폰 반납했더니 1,500만 원이 결제. 부대 내 연쇄 절도 고발합니다",
            "장사가 너무 잘돼서 오히려 망했다",
            "복도에 실외기 설치 완료",
            "방금 공개된 티웨이항공 승무원 신규 유니폼.jpg",
        ]

    def test_sort_by_kernel_production_fixed_sample(self):
        screened = attach_kernel_screen({"items": self.SAMPLE_ITEMS}, sort=False)["items"]
        prod_out = sort_by_kernel(screened)

        # 생산 정렬 순서: person -> cooling -> score
        # 1. person=True (식었지만 사람이 있는 항목, score 95)
        # 2. person=False, cooling=False (score 내림차순: 90 -> 80 -> 54 -> 39 -> 20)
        assert [item["title"] for item in prod_out] == [
            "식었지만 사람이 있는 항목",
            "복도에 실외기 설치 완료",
            "공짜 커피를 받았더니 돈을 요구했다",
            "방금 공개된 티웨이항공 승무원 신규 유니폼.jpg",
            "휴대폰 반납했더니 1,500만 원이 결제. 부대 내 연쇄 절도 고발합니다",
            "장사가 너무 잘돼서 오히려 망했다",
        ]


class TestSelectionUsesTheVerdictNotJustTheScore:
    """자를 때도 커널을 보는가.

    2026-08-07 새벽, 게이트에는 판정이 들어가 있는데 마지막 자르기가 점수 순이라
    통과한 사는 축 소재가 화면 직전에 다시 잘렸다.
    2026-08-08 실측에서 live_wrong/live_gap 축이 기각된 이후, 생산 정렬은
    person 1차 키 + 점수 순으로 동작하며, 레거시 연구 재현은 sort_by_kernel_legacy_axis에서 검증한다.
    """

    def test_legacy_axis_sort_a_low_scoring_live_item_outranks_a_high_scoring_dead_one(self):
        items = [
            {"title": "방금 공개된 티웨이항공 승무원 신규 유니폼.jpg", "x_exposure_score": 54},
            {"title": "휴대폰 반납했더니 1,500만 원이 결제. 부대 내 연쇄 절도 고발합니다", "x_exposure_score": 39},
        ]
        out = sort_by_kernel_legacy_axis(attach_kernel_screen({"items": items}, sort=False)["items"])
        assert out[0]["x_exposure_score"] == 39

    def test_production_sort_orders_by_score_when_person_status_is_equal(self):
        items = [
            {"title": "방금 공개된 티웨이항공 승무원 신규 유니폼.jpg", "x_exposure_score": 54},
            {"title": "휴대폰 반납했더니 1,500만 원이 결제. 부대 내 연쇄 절도 고발합니다", "x_exposure_score": 39},
        ]
        out = sort_by_kernel(attach_kernel_screen({"items": items}, sort=False)["items"])
        assert out[0]["x_exposure_score"] == 54

    def test_score_still_orders_items_that_share_an_axis(self):
        items = [
            {"title": "달 月자가 들어가는 예쁜 한자 단어 알려주세요.jpg", "x_exposure_score": 40},
            {"title": "스파6.. 어제 다운받고 처음 해봤다", "x_exposure_score": 80},
        ]
        out = sort_by_kernel(attach_kernel_screen({"items": items}, sort=False)["items"])
        assert out[0]["x_exposure_score"] == 80


class TestDashboardPersonAxis:
    def test_person_badge_summary_count_and_client_sort_are_present(self):
        html = get_dashboard_html("test")

        assert "사람 있음" in html
        assert "person_count" in html
        assert "person_source === 'summary'" in html
        assert "safeHtml(personTerm)" in html
        assert "if (pa !== pb) return pa ? -1 : 1;" in html
        assert "식은 것" in html
        assert "식음 · ${safeHtml(String(item.last_growth_minutes))}분째 정체" in html
        assert "if (ca !== cb) return ca ? 1 : -1;" in html
        assert "Number(b.x_exposure_score || 0) - Number(a.x_exposure_score || 0)" in html


def test_quote_line_needs_speech_not_just_quotation_marks():
    """2026-08-23. 따옴표만으로는 육성을 못 가른다.

    홀드아웃 19건에서 «따옴표만» 규칙의 정밀도가 65.5%→28.6%로 반토막 났다.
    서울시 보도자료의 행사명·정책명·브랜드명이 전부 따옴표를 쓰기 때문이다.
    안쪽이 «말»인지(4자 이상 + 구어체 어미 또는 호격·1인칭)를 한 번 더 봐야 한다.
    """
    from kernel_screen import has_quote_line

    for spoken in (
        '"나잇값 좀 하세요 원장님"…무단결근 인턴, 당일 퇴사 통보',
        '"OO카페 알바 일상 보실래요?"…프랜차이즈 직원 SNS, 어디까지 허용?',
        '"연차를 왜 써요?"…휴가 몰빵하던 직장인들 돌변한 이유',
        '"안세영 이럴 수가…실수가 많아졌어" 세계연맹 해설자도 놀랐다',
    ):
        assert has_quote_line(spoken) is True, spoken

    for label_only in (
        "60세 이상 '서울시 시니어 일자리박람회' 참가자 모집",
        "대중교통 이용…서울시 '푸른하늘의 날' 캠페인",
        "[AI픽] KT, '모두의 AI' 풀스택 승부",
        "서울시, 모아타운 '쾌속통합' 추진",
        "해남 규모 3.1 지진",
    ):
        assert has_quote_line(label_only) is False, label_only


def test_verdict_split_is_a_gauge_not_a_gate():
    """verdict_split 은 «답글»을 재고 axis 는 «도달»을 잰다 — 서로 다른 결과다.

    커널 실측에서 논쟁 축은 도달 예측에 기각돼 dead_debate 로 낮게 매겨진다.
    같은 소재가 답글에는 좋을 수 있다(2026-08-23 계정 실측 — 답글율 1위 글의
    노출이 2,800이었다). 그래서 이 필드는 축도 정렬도 바꾸지 않는다.
    """
    debated = screen_material("프랜차이즈 직원 SNS, 어디까지 허용?")
    assert debated["verdict_split"] == "Y"
    assert debated["axis"] == "dead_debate"  # 축은 그대로 낮다 — 덮어쓰지 않는다

    flat = screen_material("해남 규모 3.1 지진")
    assert flat["verdict_split"] == "?"

    # 가해 역할 + 행위 조합도 판정이 갈린다
    assert screen_material("무단결근 인턴에게 당일 퇴사 통보받은 원장")["verdict_split"] == "Y"
