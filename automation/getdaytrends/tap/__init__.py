"""
TAP (Trend Arbitrage Publisher) — 교차국가 트렌드 시차 감지 엔진.

핵심 아이디어:
  국가 A에서 이미 트렌딩이지만 국가 B에서는 아직 안 뜬 키워드를 감지하고,
  국가 B에서 "곧 터질" 타이밍에 선점 발행하여 engagement를 극대화한다.

Usage:
    from edape.tap import detect_arbitrage_opportunities
    opportunities = await detect_arbitrage_opportunities(conn, config)
"""

from .detector import TrendArbitrageDetector, ArbitrageOpportunity
from .analyzer import ArbitrageAnalyzer
from .product_feed import (
    OpportunityTier,
    TapBoard,
    TapBoardBuilder,
    TapBoardItem,
    empty_tap_board,
    required_tap_product_dependencies,
)
from .deal_room import (
    DealRoomOffer,
    DealRoomRequest,
    TapDealRoom,
    TapDealRoomBuilder,
    build_tap_deal_room_snapshot,
    required_tap_deal_room_dependencies,
)
from .service import (
    TapAlertDispatchSummary,
    TapBoardRequest,
    TapRefreshSummary,
    build_tap_board_snapshot,
    dispatch_tap_alert_queue,
    get_latest_tap_board_snapshot,
    refresh_tap_market_surfaces,
)

__all__ = [
    "TrendArbitrageDetector",
    "ArbitrageOpportunity",
    "ArbitrageAnalyzer",
    "OpportunityTier",
    "TapBoard",
    "TapBoardBuilder",
    "TapBoardItem",
    "DealRoomOffer",
    "DealRoomRequest",
    "TapDealRoom",
    "TapDealRoomBuilder",
    "TapAlertDispatchSummary",
    "TapBoardRequest",
    "TapRefreshSummary",
    "build_tap_board_snapshot",
    "build_tap_deal_room_snapshot",
    "dispatch_tap_alert_queue",
    "get_latest_tap_board_snapshot",
    "refresh_tap_market_surfaces",
    "empty_tap_board",
    "required_tap_product_dependencies",
    "required_tap_deal_room_dependencies",
    "detect_arbitrage_opportunities",
]


async def detect_arbitrage_opportunities(conn, config=None) -> list[ArbitrageOpportunity]:
    """편의 진입점: 교차국가 차익거래 기회 감지.

    Args:
        conn: DB connection (aiosqlite or pg adapter)
        config: AppConfig (optional — countries 목록 추출용)

    Returns:
        ArbitrageOpportunity 리스트 (priority 내림차순)
    """
    detector = TrendArbitrageDetector(conn)
    return await detector.detect(config=config)
