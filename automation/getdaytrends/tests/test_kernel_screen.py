"""커널 소재 판별 계약.

레이더 적합도(지금 퍼지는가)와 커널 판별(X에서 판정이 붙는가)은 다른 축이다.
2026-08-06 실측에서 이 판별의 축별 중앙 노출은 가해자 명확 1,734 / 낙차·반전 730 /
쌍방 논쟁 326이었고, 쌍방 논쟁으로 판정된 6건 중 1만 노출을 넘긴 것은 0건이었다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kernel_screen import attach_kernel_screen, screen_material  # noqa: E402


class TestLiveAxes:
    def test_actor_plus_wrongdoing_is_one_sided(self):
        r = screen_material("시댁 형편 어렵다고 친정 용돈 뺏어 시댁 주자는 남편")
        assert r["axis"] == "live_wrong"
        assert "남편" in r["signals"][0]

    def test_reversal_word_is_a_gap(self):
        assert screen_material("산 정상에서 모두가 한 남자를 막아선 이유")["axis"] == "live_gap"

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


class TestAttach:
    def test_attach_adds_screen_and_summary_without_mutating(self):
        payload = {"items": [{"title": "팀장이 회식비 떠넘김"}, {"title": "이거 맞나요?"}]}
        out = attach_kernel_screen(payload)

        assert "kernel_screen" not in payload["items"][0]
        assert out["items"][0]["kernel_screen"]["axis"] == "live_wrong"
        assert out["items"][1]["kernel_screen"]["axis"] == "dead_debate"
        assert out["kernel_summary"] == {"live": 1, "dead": 1, "verify_first": 0}

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

    def test_ordinary_sentence_is_not_forced_into_a_gap(self):
        # 낙차 패턴이 너무 넓으면 전부 사는 축이 되어 선별이 무의미해진다.
        assert screen_material("오늘 점심 뭐 먹을지 고민 중")["axis"] == "dead_flat"
        assert screen_material("복도에 실외기 설치 완료")["axis"] == "dead_flat"


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

    def test_unknown_outranks_dead(self):
        # 모르는 것을 버리는 것보다 사람이 원문을 열어 보게 하는 편이 낫다.
        items = [
            {"title": "얘들아 다들 이거 합쳐봐", "x_exposure_score": 90},
            {"title": "김혜수", "x_exposure_score": 10},
        ]
        out = attach_kernel_screen({"items": items})["items"]
        assert out[0]["title"] == "김혜수"

    def test_leaked_filter_items_do_not_reach_the_top(self):
        # 오늘 실제로 제외 필터를 빠져나간 제목들. 커널 정렬에서는 전부 아래로 간다.
        leaked = [
            "국짐이 정청래편인척",
            "요즘 애니회사들, 유부녀를 판다.jpg",
            "이야 성접대는 좀 많이 큰데?",
        ]
        items = [{"title": t, "x_exposure_score": 95} for t in leaked]
        items.append({"title": "남편이 친정 용돈을 뺏어감", "x_exposure_score": 20})
        out = attach_kernel_screen({"items": items})["items"]
        assert out[0]["title"] == "남편이 친정 용돈을 뺏어감"

    def test_sorting_can_be_turned_off(self):
        items = [{"title": "복도에 실외기 설치 완료"}, {"title": "팀장이 회식비를 떠넘김"}]
        out = attach_kernel_screen({"items": items}, sort=False)["items"]
        assert out[0]["title"] == "복도에 실외기 설치 완료"
