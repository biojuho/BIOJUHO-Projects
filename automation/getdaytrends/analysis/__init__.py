"""analysis/ — Trend Analysis Package for getdaytrends.

analyzer.py에서 추출된 스코어링 및 파싱 모듈.

공개 API:
    analyze_trends(raw_trends, contexts, config, conn) -> list[ScoredTrend]
    _compute_signal_score(...) -> float
    _compute_cross_source_confidence(...) -> int
    _compute_freshness_score(...) -> float
    _parse_scored_trend_from_dict(...) -> ScoredTrend
"""

from analysis.scoring import (  # noqa: F401
    _compute_cross_source_confidence,
    _compute_freshness_score,
    _compute_signal_score,
)
from analysis.parsing import (  # noqa: F401
    _default_scored_trend,
    _parse_json,
    _parse_json_array,
    _parse_scored_trend_from_dict,
    _score_batch_instructor,
)
