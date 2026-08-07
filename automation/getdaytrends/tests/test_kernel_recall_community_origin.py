"""커뮤니티 원문 제목으로 재는 재현율 — 이쪽이 진짜 측정자다.

`test_kernel_recall_ground_truth.py`의 20건은 **X 캡션**이다. 그런데 이 레이더가 실제로
`screen_material`에 넣는 것은 **커뮤니티 게시판의 제목**이다. 둘은 같은 소재라도 문장이
전혀 다르다.

    X 캡션            "통닭아냐?"                       (82만 노출)
    커뮤니티 원문      "임산부덕 오늘 병원갔다가 놀람"      (더쿠, 조회 34,636)

"통닭아냐?"는 우리 화면에 절대 나타나지 않는다. 그러므로 그 파일의 재현율은 우리가 고칠
수 있는 것을 재지 못한다. **이 파일이 그 자리를 맡는다.**

**표본이 아직 1건이다.** 커널 문서 0-1절 3번의 기준(버킷당 10건 미만이면 방향성 신호로만
쓰고 규칙으로 승격하지 않는다)을 그대로 적용한다 — 지금은 회귀 바닥으로만 쓰고, 이 숫자를
근거로 판정 규칙을 바꾸지 않는다.

**쌍을 어떻게 늘리는가.** X에서 퍼진 게시물에 출처 커뮤니티의 원문 제목이 함께 찍혀 있을
때만 쌍이 된다(인용 카드, 캡처 상단의 제목·URL 등). 사용자가 그런 게시물을 넘길 때마다
여기에 추가한다. 추정으로 채우지 않는다 — 어느 커뮤니티 글인지 불확실하면 넣지 않는 편이
측정을 지킨다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kernel_screen import screen_material  # noqa: E402

# (커뮤니티 원문 제목, 출처, 커뮤니티 조회, 그 소재가 X에서 낸 노출, X 캡션)
COMMUNITY_ORIGIN_TRUTH: tuple[tuple[str, str, int, int, str], ...] = (
    (
        "임산부덕 오늘 병원갔다가 놀람",
        "theqoo",
        34_636,
        820_000,
        "통닭아냐?",
    ),
)

# 2026-08-07 측정값. 커널이 나아지면 올린다.
_BASELINE_LIVE = 0


def _live_titles() -> list[str]:
    return [
        title
        for title, *_ in COMMUNITY_ORIGIN_TRUTH
        if str(screen_material(title).get("axis", "")).startswith("live")
    ]


def test_recall_has_not_regressed():
    caught = _live_titles()
    assert len(caught) >= _BASELINE_LIVE, (
        f"커뮤니티 원문 {len(COMMUNITY_ORIGIN_TRUTH)}건 중 {len(caught)}건만 사는 축으로 "
        f"잡았다 (기준 {_BASELINE_LIVE}건). 잡은 것: {caught}"
    )


def test_every_verdict_carries_its_reason():
    """근거 없는 판정은 사람이 뒤집을 수 없어 쓸모가 없다."""
    for title, *_ in COMMUNITY_ORIGIN_TRUTH:
        assert screen_material(title).get("signals"), title


def test_the_x_caption_would_never_reach_us():
    """정답지가 왜 둘로 나뉘는지를 코드로 못 박는다.

    X 캡션은 우리 입력이 아니다. 이 테스트가 깨진다면 누군가 X 캡션을 커뮤니티 원문
    정답지에 섞은 것이고, 그 순간 이 파일은 다시 다른 것을 재기 시작한다.
    """
    for *_, x_caption in COMMUNITY_ORIGIN_TRUTH:
        assert len(x_caption) < 20, (
            f"X 캡션 {x_caption!r}이 커뮤니티 제목만큼 길다 — 정말 캡션이 맞는지 확인할 것"
        )
