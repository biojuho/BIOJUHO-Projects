"""실제로 퍼진 소재를 커널이 잡는가 — 재현율 정답지.

2026-08-07에 사용자가 넘긴 X 실측 20건이다. 8/5~8/6에 올라와 22만~138만 노출을 낸
게시물들로, 이 프로젝트가 "X에서 판정이 붙는 소재"를 고르는 도구인 이상 실제로 붙은
소재를 얼마나 잡는지가 이 판정의 재현율이다. 측정하니 **2/20(10%)**이었다.

**이 숫자만 쫓으면 안 된다.** 커널 문서(`hook-kernel-v1.4.md`) 0-1절 4번이 경고하듯
이 표본은 성공작만 모은 것이라 재현율은 재도 정밀도는 재지 못한다. 모든 제목을 사는
축으로 판정하면 이 파일은 만점이 되지만 선별은 무의미해진다. 정밀도 쪽은
`test_kernel_screen.py`의 `test_ordinary_sentence_is_not_forced_into_a_gap`과
`TestSortingPutsLiveMaterialFirst`가 지킨다. **두 파일을 같이 봐야 한다.**

여기 적힌 기대값은 2026-08-07 기준이다. 커널을 고쳐 더 잡게 되면 `_BASELINE_LIVE`를
올려 갱신한다 — 내려가면 회귀다.

측정 당시 놓친 것 중 낙차가 뚜렷한 사례(어휘 목록의 한계를 보여 준다):
  - "《유치원 한복 대참사...》" 133만 — 시녀처럼 보임 → 이듬해 중전마마 룩
  - "진정한 명품 아파트" 56만 — 명품이라는 말이 시설기사 성금모금으로 착지
  - "회사 생활의 무서움" 89만 — 상했다던 계란이 회사에 두니 멀쩡해짐
  - "에어컨에게 사과하다 뜬금 냉장고에게 숙연해지는 중.." 35만 — 대상 전환
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from content_filters import excluded_topic_reason  # noqa: E402
from kernel_screen import screen_material  # noqa: E402

# (제목, 노출) — 2026-08-06~07 X 실측
VIRAL_GROUND_TRUTH: tuple[tuple[str, int], ...] = (
    ("3일 동안 무슬림으로 살아보기 찍다가 진짜 무슬림이 된 유튜버 근황", 1_380_000),
    ("《유치원 한복 대참사...》", 1_330_000),
    ("80kg 여성이 쓴 글에 유도갤 반응 지금봐도 개명언인듯", 1_250_000),
    ("고양이 쉼터에서 모르고 6시간 잔 사람", 1_240_000),
    ("오디세이 용아맥 후기 찾아보는데 냄새난단 말밖에 없네 ㅅㅂ", 1_230_000),
    ("회사 생활의 무서움", 890_000),
    ("머리를 띵하게 만든 글", 860_000),
    ("[딱 3주간 이렇게 저녁에 먹으면 최소 7키로 감량 성공]", 740_000),
    ("친구와이프 임신했는데 배 만진 사람", 710_000),
    ("정부가 만 35세 미만 청년이 자발적으로 퇴사해도 생애 한 번 실업급여를 받을 수 있도록 추진 중", 710_000),
    ("요즘 젊은 애들이 채팅할 때 안쓰는 표현", 570_000),
    ("진정한 명품 아파트", 560_000),
    ("농심배 짜파게티 대회에서 우승한 작품", 480_000),
    ("어느 식당이 여름 휴가를 간 이유", 410_000),
    ("에어컨에게 사과하다 뜬금 냉장고에게 숙연해지는 중..", 350_000),
    ("복숭아 품종 진짜 다양한데 내가 맛있게 먹은게 뭐였는지 몰랐는데", 340_000),
    ("더울땐 돈 아끼지 맙시다.", 340_000),
    ("충청도는 새싹부터 다르구나", 310_000),
    ("거짓말", 230_000),
    ("진짜 배려는 받은 사람의 기억에 평생 남는다", 220_000),
)

# 2026-08-07 측정값 → 0005 검수 후 3으로 조정.
# 과적합 패턴 5종 제거(상태 변환·시간 과잉·관계-신체·기대-평가·인지 반전),
# 순수 구조 1종(대상 전환)만 유지. 어휘 판정(근황·이유) 포함 3건.
_BASELINE_LIVE = 3

# 그때 잡은 두 건. 둘 다 어휘 하나로 걸렸다("근황", "이유") — 판별력이라기보다 우연에 가깝다.
_KNOWN_HITS = (
    "3일 동안 무슬림으로 살아보기 찍다가 진짜 무슬림이 된 유튜버 근황",
    "어느 식당이 여름 휴가를 간 이유",
)


def _live_titles() -> list[str]:
    return [
        title
        for title, _ in VIRAL_GROUND_TRUTH
        if str(screen_material(title).get("axis", "")).startswith("live")
    ]


def test_recall_has_not_regressed():
    caught = _live_titles()
    assert len(caught) >= _BASELINE_LIVE, (
        f"실제로 퍼진 20건 중 {len(caught)}건만 사는 축으로 잡았다 "
        f"(기준 {_BASELINE_LIVE}건). 잡은 것: {caught}"
    )


@pytest.mark.parametrize("title", _KNOWN_HITS)
def test_the_two_it_used_to_catch_are_still_caught(title):
    assert str(screen_material(title).get("axis", "")).startswith("live")


def test_every_verdict_carries_its_reason():
    """근거 없는 판정은 사람이 뒤집을 수 없어 쓸모가 없다."""
    for title, _ in VIRAL_GROUND_TRUTH:
        assert screen_material(title).get("signals"), title


def test_a_cooking_contest_is_not_a_sports_event():
    """2026-08-07: '대회에서 우승' 스포츠 오탐. 0007에서 패턴을 좁혀 해제."""
    assert excluded_topic_reason("농심배 짜파게티 대회에서 우승한 작품") is None
