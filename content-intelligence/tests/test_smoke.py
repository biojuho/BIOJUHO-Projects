"""Content Intelligence Engine (CIE) v2.0 — 스모크 테스트.

핵심 모듈의 import, 데이터 모델 생성, 설정 로드를 검증한다.
외부 API 호출 없이 단위 수준으로 실행된다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ── CIE 루트를 PYTHONPATH에 추가 ──
_CIE_DIR = Path(__file__).resolve().parents[1]
if str(_CIE_DIR) not in sys.path:
    sys.path.insert(0, str(_CIE_DIR))

_PROJECT_ROOT = _CIE_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ═══════════════════════════════════════════════════
#  1. Import 검증
# ═══════════════════════════════════════════════════

class TestImports:
    """핵심 모듈이 정상 import 되는지 확인한다."""

    def test_import_config(self):
        from config import CIEConfig
        assert CIEConfig is not None

    def test_import_models(self):
        from storage.models import (
            PlatformTrend,
            PlatformTrendReport,
            MergedTrendReport,
            RegulationReport,
            UnifiedChecklist,
            QAReport,
            GeneratedContent,
            ContentBatch,
            PublishResult,
        )
        assert PlatformTrend is not None
        assert ContentBatch is not None
        assert PublishResult is not None

    def test_import_collectors_base(self):
        from collectors.base import _parse_json_response, _tier_from_str
        assert callable(_parse_json_response)
        assert callable(_tier_from_str)

    def test_import_gdt_bridge(self):
        from collectors.gdt_bridge import (
            load_all,
            load_rich_trends,
            load_posting_stats,
            load_top_performing_keywords,
            load_watchlist_alerts,
            RichTrend,
            GdtBridgeResult,
        )
        assert callable(load_all)
        assert RichTrend is not None

    def test_import_notion_publisher(self):
        from storage.notion_publisher import publish_to_notion, publish_batch_to_notion
        assert callable(publish_to_notion)
        assert callable(publish_batch_to_notion)

    def test_import_x_publisher(self):
        from storage.x_publisher import publish_to_x, publish_batch_to_x
        assert callable(publish_to_x)
        assert callable(publish_batch_to_x)


# ═══════════════════════════════════════════════════
#  2. 데이터 모델 생성 검증
# ═══════════════════════════════════════════════════

class TestModels:
    """데이터 모델이 올바르게 생성되는지 확인한다."""

    def test_platform_trend_defaults(self):
        from storage.models import PlatformTrend
        trend = PlatformTrend(keyword="AI 자동화")
        assert trend.keyword == "AI 자동화"
        assert trend.volume == 0
        assert trend.hashtags == []

    def test_platform_trend_v2_fields(self):
        """v2.0 확장 필드 검증."""
        from storage.models import PlatformTrend
        trend = PlatformTrend(
            keyword="LLM 혁신",
            sentiment="positive",
            confidence=85,
            hook_starter="당신이 놓치고 있는 LLM 트렌드",
            optimal_post_hour=14,
        )
        assert trend.sentiment == "positive"
        assert trend.confidence == 85
        assert trend.hook_starter != ""
        assert trend.optimal_post_hour == 14

    def test_qa_report_scoring(self):
        from storage.models import QAReport
        qa = QAReport(
            hook_score=18,
            fact_score=13,
            tone_score=14,
            kick_score=12,
            angle_score=13,
            regulation_score=8,
            algorithm_score=9,
        )
        assert qa.total_score == 87
        assert qa.pass_threshold is True

    def test_qa_report_fail(self):
        from storage.models import QAReport
        qa = QAReport(hook_score=5, fact_score=5, tone_score=5)
        assert qa.total_score == 15
        assert qa.pass_threshold is False

    def test_merged_trend_report_summary(self):
        from storage.models import (
            PlatformTrend,
            PlatformTrendReport,
            MergedTrendReport,
        )
        trend = PlatformTrend(
            keyword="LLM",
            volume=1200,
            format_trend="쓰레드",
            tone_trend="교육",
        )
        report = PlatformTrendReport(platform="x", trends=[trend])
        merged = MergedTrendReport(
            platform_reports=[report],
            top_insights=["LLM이 핫하다"],
        )
        text = merged.to_summary_text()
        assert "X 트렌드" in text
        assert "LLM" in text

    def test_merged_trend_v2_summary(self):
        """v2.0 감성/신뢰도 필드가 summary에 반영되는지 확인."""
        from storage.models import (
            PlatformTrend,
            PlatformTrendReport,
            MergedTrendReport,
        )
        trend = PlatformTrend(
            keyword="GPT-5",
            sentiment="positive",
            confidence=90,
            hook_starter="GPT-5가 바꿀 세계",
        )
        report = PlatformTrendReport(platform="x", trends=[trend])
        merged = MergedTrendReport(platform_reports=[report])
        text = merged.to_summary_text()
        assert "감성" in text
        assert "Hook" in text

    def test_unified_checklist_text(self):
        from storage.models import UnifiedChecklist
        checklist = UnifiedChecklist(
            do_items=[{"platform": "x", "action": "해시태그 3개 미만"}],
            dont_items=[{"platform": "threads", "action": "외부 링크 금지", "severity": "높음"}],
            summary="테스트 체크리스트",
        )
        text = checklist.to_checklist_text()
        assert "DO" in text
        assert "DON'T" in text
        assert "외부 링크 금지" in text

    def test_content_batch_summary(self):
        from storage.models import GeneratedContent, ContentBatch, QAReport
        content = GeneratedContent(
            platform="x",
            content_type="post",
            body="테스트 포스트",
            qa_report=QAReport(
                hook_score=15, fact_score=12, tone_score=12,
                kick_score=11, angle_score=11,
                regulation_score=8, algorithm_score=8,
            ),
        )
        batch = ContentBatch(contents=[content])
        assert batch.all_passed is True
        assert "1건" in batch.summary()

    def test_content_publish_metadata(self):
        """v2.0 발행 메타데이터 검증."""
        from datetime import datetime
        from storage.models import GeneratedContent
        content = GeneratedContent(
            platform="x",
            content_type="post",
            body="발행 테스트",
        )
        assert content.is_published is False
        assert content.publish_target == ""

        content.published_at = datetime.now()
        content.publish_target = "notion"
        content.notion_page_id = "abc-123"
        assert content.is_published is True

    def test_publish_result(self):
        from storage.models import PublishResult
        result = PublishResult(
            platform="x",
            success=True,
            target="notion",
            page_id="test-page-id",
        )
        assert result.success is True
        assert result.page_id == "test-page-id"


# ═══════════════════════════════════════════════════
#  3. 설정(Config) 검증
# ═══════════════════════════════════════════════════

class TestConfig:
    """CIEConfig 설정이 올바르게 로드되는지 확인한다."""

    def test_config_defaults(self):
        from config import CIEConfig
        config = CIEConfig()
        assert config.trend_top_n == 5
        assert config.enable_qa_validation is True
        assert config.qa_min_score == 70

    def test_config_tier_mapping(self):
        from config import CIEConfig
        config = CIEConfig()
        assert config.get_tier("trend") == config.trend_analysis_tier
        assert config.get_tier("content") == config.content_generation_tier
        assert config.get_tier("unknown") == "LIGHTWEIGHT"

    def test_config_summary(self):
        from config import CIEConfig
        config = CIEConfig()
        summary = config.summary()
        assert "플랫폼" in summary
        assert "QA" in summary

    def test_config_v2_defaults(self):
        """v2.0 발행 설정 기본값 검증."""
        from config import CIEConfig
        config = CIEConfig()
        # 기본값: 발행 비활성
        assert config.enable_notion_publish is False
        assert config.enable_x_publish is False
        assert config.x_min_qa_score == 75

    def test_config_summary_v2(self):
        """v2.0 summary에 발행/GDT 정보 포함 확인."""
        from config import CIEConfig
        config = CIEConfig()
        summary = config.summary()
        assert "발행" in summary
        assert "GDT DB" in summary


# ═══════════════════════════════════════════════════
#  4. 유틸리티 함수
# ═══════════════════════════════════════════════════

class TestUtils:
    """유틸리티 함수들이 올바르게 동작하는지 확인한다."""

    def test_parse_json_from_code_block(self):
        from collectors.base import _parse_json_response
        raw = '```json\n{"key": "value"}\n```'
        result = _parse_json_response(raw)
        assert result == {"key": "value"}

    def test_parse_json_plain(self):
        from collectors.base import _parse_json_response
        raw = '{"a": 1, "b": 2}'
        result = _parse_json_response(raw)
        assert result == {"a": 1, "b": 2}

    def test_parse_json_with_prefix(self):
        from collectors.base import _parse_json_response
        raw = 'Here is the result: {"status": "ok"} end.'
        result = _parse_json_response(raw)
        assert result["status"] == "ok"

    def test_tier_from_str(self):
        from collectors.base import _tier_from_str
        from shared.llm import TaskTier
        assert _tier_from_str("LIGHTWEIGHT") == TaskTier.LIGHTWEIGHT
        assert _tier_from_str("heavy") == TaskTier.HEAVY
        assert _tier_from_str("MEDIUM") == TaskTier.MEDIUM
        assert _tier_from_str("unknown") == TaskTier.LIGHTWEIGHT

    def test_regulation_merge_common(self):
        from regulators.checklist import _merge_common
        items = [
            {"platform": "x", "action": "해시태그 사용", "priority": "높음"},
            {"platform": "threads", "action": "해시태그 사용", "priority": "높음"},
            {"platform": "naver", "action": "제목 최적화", "priority": "중"},
        ]
        _merge_common(items, "priority")
        assert len(items) == 2
        common = [i for i in items if i["platform"] == "공통"]
        assert len(common) == 1
        assert common[0]["action"] == "해시태그 사용"


# ═══════════════════════════════════════════════════
#  5. GDT Bridge 검증
# ═══════════════════════════════════════════════════

class TestGdtBridge:
    """GDT Bridge 모듈의 데이터 모델과 로직 검증."""

    def test_rich_trend_creation(self):
        from collectors.gdt_bridge import RichTrend
        trend = RichTrend(
            keyword="AI Agent",
            viral_potential=85,
            sentiment="positive",
            confidence=90,
        )
        assert trend.keyword == "AI Agent"
        assert trend.viral_potential == 85

    def test_gdt_bridge_result_defaults(self):
        from collectors.gdt_bridge import GdtBridgeResult
        result = GdtBridgeResult()
        assert result.trends == []
        assert result.posting_slots == []
        assert result.db_path == ""

    def test_posting_time_slot(self):
        from collectors.gdt_bridge import PostingTimeSlot
        slot = PostingTimeSlot(
            category="AI",
            hour=14,
            avg_score=85.5,
            sample_count=25,
        )
        assert slot.hour == 14
        assert slot.avg_score == 85.5


# ═══════════════════════════════════════════════════
#  6. DB 스키마 검증
# ═══════════════════════════════════════════════════

class TestLocalDB:
    """로컬 DB 스키마 v2.0 검증."""

    def test_schema_creation(self, tmp_path):
        """임시 DB에 스키마가 정상 생성되는지 확인."""
        from config import CIEConfig
        from storage.local_db import get_connection

        config = CIEConfig()
        config.sqlite_path = str(tmp_path / "test_cie.db")
        conn = get_connection(config)

        # generated_contents에 발행 컬럼 존재 확인
        cursor = conn.execute("PRAGMA table_info(generated_contents)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "published_at" in columns
        assert "publish_target" in columns
        assert "notion_page_id" in columns
        assert "publish_error" in columns

        # trend_reports에 v2.0 컬럼 존재 확인
        cursor = conn.execute("PRAGMA table_info(trend_reports)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "sentiment" in columns
        assert "confidence" in columns
        assert "hook_starter" in columns

        conn.close()

    def test_load_unpublished_empty(self, tmp_path):
        """빈 DB에서 미발행 로드가 빈 리스트를 반환하는지 확인."""
        from config import CIEConfig
        from storage.local_db import get_connection, load_unpublished_contents

        config = CIEConfig()
        config.sqlite_path = str(tmp_path / "test_cie2.db")
        conn = get_connection(config)
        contents = load_unpublished_contents(conn)
        assert contents == []
        conn.close()
