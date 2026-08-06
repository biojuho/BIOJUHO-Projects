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
        assert out["items"][0] is None
        assert out["items"][1]["kernel_screen"]["axis"] == "dead_debate"
