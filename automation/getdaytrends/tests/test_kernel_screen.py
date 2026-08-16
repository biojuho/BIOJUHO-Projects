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
