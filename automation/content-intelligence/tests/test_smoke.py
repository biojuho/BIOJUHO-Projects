"""Content Intelligence Engine (CIE) v2.0 — 스모크 테스트.

핵심 모듈의 import, 데이터 모델 생성, 설정 로드를 검증한다.
외부 API 호출 없이 단위 수준으로 실행된다.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
            ContentBatch,
            PlatformTrend,
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
            RichTrend,
            load_all,
        )

        assert callable(load_all)
        assert RichTrend is not None

    def test_import_notion_publisher(self):
        from storage.notion_publisher import publish_batch_to_notion, publish_to_notion

        assert callable(publish_to_notion)
        assert callable(publish_batch_to_notion)

    def test_import_x_publisher(self):
        from storage.x_publisher import publish_batch_to_x, publish_to_x

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
            MergedTrendReport,
            PlatformTrend,
            PlatformTrendReport,
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
            MergedTrendReport,
            PlatformTrend,
            PlatformTrendReport,
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
        from storage.models import ContentBatch, GeneratedContent, QAReport

        content = GeneratedContent(
            platform="x",
            content_type="post",
            body="테스트 포스트",
            qa_report=QAReport(
                hook_score=15,
                fact_score=12,
                tone_score=12,
                kick_score=11,
                angle_score=11,
                regulation_score=8,
                algorithm_score=8,
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

    def test_write_content_feedback_no_db(self, tmp_path):
        """GDT DB 없을 때 역피드백이 False 반환하고 예외 없이 종료.

        project_root를 tmp_path로 격리해 기본 candidate 경로에서
        실제 getdaytrends.db가 탐지되지 않도록 한다.
        """
        from config import CIEConfig
        from collectors.gdt_bridge import write_content_feedback

        config = CIEConfig()
        config.gdt_db_path = str(tmp_path / "nonexistent.db")
        # fallback candidate 탐색도 막기 위해 project_root를 빈 임시 디렉터리로 격리
        config.project_root = tmp_path
        result = write_content_feedback(config, "AI", "x", 85.0)
        assert result is False

    def test_write_content_feedback_batch_empty(self):
        """빈 배치 입력 시 0 반환."""
        from config import CIEConfig
        from collectors.gdt_bridge import write_content_feedback_batch

        config = CIEConfig()
        result = write_content_feedback_batch(config, [])
        assert result == 0

    def test_write_content_feedback_batch_with_db(self, tmp_path):
        """임시 GDT DB에 content_feedback 배치 주입 검증."""
        import sqlite3

        from config import CIEConfig
        from collectors.gdt_bridge import write_content_feedback_batch

        # 임시 GDT DB 생성 (content_feedback 테이블만)
        db_path = tmp_path / "gdt_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """CREATE TABLE content_feedback (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               keyword TEXT NOT NULL,
               category TEXT DEFAULT '',
               qa_score REAL DEFAULT 0.0,
               regenerated INTEGER DEFAULT 0,
               reason TEXT DEFAULT '',
               content_age_hours REAL DEFAULT 0.0,
               freshness_grade TEXT DEFAULT 'unknown',
               created_at TEXT NOT NULL
            )"""
        )
        conn.commit()
        conn.close()

        config = CIEConfig()
        config.gdt_db_path = str(db_path)

        items = [
            {"keyword": "AI 자동화", "category": "x", "qa_score": 87.0, "regenerated": False, "reason": ""},
            {"keyword": "LLM 트렌드", "category": "threads", "qa_score": 72.0, "regenerated": True, "reason": "hook 미달"},
        ]
        written = write_content_feedback_batch(config, items)
        assert written == 2

        # DB에서 확인
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT keyword, qa_score, regenerated FROM content_feedback ORDER BY id").fetchall()
        conn.close()
        assert len(rows) == 2
        assert rows[0][0] == "AI 자동화"
        assert rows[0][1] == 87.0
        assert rows[1][2] == 1  # regenerated=True → 1

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


# ═══════════════════════════════════════════════════════
#  Phase 1 테스트: 페르소나, 보조 QA 축, Naver SEO
# ═══════════════════════════════════════════════════════


class TestPersonas:
    """독자 페르소나 시스템 테스트."""

    def test_load_personas_from_file(self, tmp_path):
        """personas.json이 있으면 정상 로드."""
        import json

        from config import CIEConfig

        personas_data = [
            {"id": "test_persona", "name": "테스트", "pain_points": ["문제1"]}
        ]
        pf = tmp_path / "personas.json"
        pf.write_text(json.dumps(personas_data, ensure_ascii=False), encoding="utf-8")

        config = CIEConfig()
        config.personas_file = str(pf)
        result = config.load_personas()
        assert len(result) == 1
        assert result[0]["id"] == "test_persona"

    def test_load_personas_missing_file(self, tmp_path):
        """personas.json이 없으면 빈 리스트 반환."""
        from config import CIEConfig

        config = CIEConfig()
        config.personas_file = str(tmp_path / "nonexistent.json")
        assert config.load_personas() == []

    def test_load_personas_invalid_json(self, tmp_path):
        """잘못된 JSON이면 빈 리스트 반환 (에러 무시)."""
        from config import CIEConfig

        pf = tmp_path / "bad.json"
        pf.write_text("{invalid", encoding="utf-8")

        config = CIEConfig()
        config.personas_file = str(pf)
        assert config.load_personas() == []

    def test_build_persona_block_with_personas(self):
        """페르소나가 있으면 컨텍스트 블록이 생성된다."""
        from prompts.content_generation import _build_persona_block

        personas = [
            {
                "id": "tester",
                "name": "테스터",
                "description": "테스트용 페르소나",
                "pain_points": ["문제A", "문제B"],
                "preferred_hooks": ["hook1"],
                "share_triggers": ["trigger1"],
                "platform_affinity": ["x"],
            }
        ]
        block = _build_persona_block("x", personas)
        assert "테스터" in block
        assert "문제A" in block
        assert "hook1" in block

    def test_build_persona_block_empty(self):
        """페르소나가 없으면 빈 문자열."""
        from prompts.content_generation import _build_persona_block

        assert _build_persona_block("x", None) == ""
        assert _build_persona_block("x", []) == ""

    def test_build_persona_block_platform_affinity(self):
        """플랫폼 친화도 기준 페르소나 선택."""
        from prompts.content_generation import _build_persona_block

        personas = [
            {
                "id": "x_user",
                "name": "X유저",
                "description": "X 전문",
                "pain_points": ["p1"],
                "preferred_hooks": [],
                "share_triggers": [],
                "platform_affinity": ["x"],
            },
            {
                "id": "naver_user",
                "name": "네이버유저",
                "description": "네이버 전문",
                "pain_points": ["p1", "p2"],
                "preferred_hooks": [],
                "share_triggers": [],
                "platform_affinity": ["naver"],
            },
        ]
        block = _build_persona_block("x", personas)
        assert "X유저" in block
        assert "네이버유저" not in block


class TestQAReportV2:
    """QAReport v2.0 보조 축 테스트."""

    def test_supplementary_scores_default_zero(self):
        """보조 3축 기본값은 0."""
        from storage.models import QAReport

        qa = QAReport()
        assert qa.reader_value_score == 0
        assert qa.originality_score == 0
        assert qa.credibility_score == 0

    def test_supplementary_scores_not_in_total(self):
        """보조 축은 total_score에 포함되지 않는다."""
        from storage.models import QAReport

        qa = QAReport(
            hook_score=20, fact_score=15, tone_score=15,
            kick_score=15, angle_score=15,
            regulation_score=10, algorithm_score=10,
            reader_value_score=10, originality_score=10, credibility_score=10,
        )
        assert qa.total_score == 100  # 보조 30점은 미포함

    def test_applied_min_score_controls_pass_threshold(self):
        """applied_min_score가 pass_threshold 판정 기준이 된다."""
        from storage.models import QAReport

        qa = QAReport(hook_score=15, fact_score=10, tone_score=10,
                      kick_score=10, angle_score=10,
                      regulation_score=7, algorithm_score=7)
        # total = 69
        assert qa.total_score == 69
        assert qa.pass_threshold is False  # 기본 applied_min_score=70

        qa.applied_min_score = 65
        assert qa.pass_threshold is True  # 65 이상이면 통과

    def test_emoji_report_includes_supplementary(self):
        """to_emoji_report()에 보조 축이 포함된다."""
        from storage.models import QAReport

        qa = QAReport(reader_value_score=8, originality_score=6, credibility_score=9)
        report = qa.to_emoji_report()
        assert "RV: 8/10" in report
        assert "Orig: 6/10" in report
        assert "Cred: 9/10" in report


class TestProQADiagnostic:
    """Pro QA 진단 시스템 테스트."""

    def test_axis_diagnostic_is_weak(self):
        """50% 미만이면 약점."""
        from storage.models import QAAxisDiagnostic

        strong = QAAxisDiagnostic(axis="hook", score=15, max_score=20)
        weak = QAAxisDiagnostic(axis="kick", score=3, max_score=15)
        assert strong.is_weak is False
        assert weak.is_weak is True

    def test_axis_diagnostic_score_ratio(self):
        from storage.models import QAAxisDiagnostic

        d = QAAxisDiagnostic(axis="tone", score=10, max_score=15)
        assert abs(d.score_ratio - 0.6667) < 0.01

    def test_qa_report_weak_axes(self):
        """weak_axes는 50% 미만 축만 반환."""
        from storage.models import QAAxisDiagnostic, QAReport

        qa = QAReport(
            hook_score=18, fact_score=3,
            diagnostics=[
                QAAxisDiagnostic(axis="hook", score=18, max_score=20),
                QAAxisDiagnostic(axis="fact", score=3, max_score=15),
            ],
        )
        weak = qa.weak_axes
        assert len(weak) == 1
        assert weak[0].axis == "fact"

    def test_persona_fit_score(self):
        from storage.models import PersonaFitScore

        pf = PersonaFitScore(persona_id="test", persona_name="테스트", fit_score=8, reason="좋음")
        assert pf.fit_score == 8

    def test_top_persona(self):
        from storage.models import PersonaFitScore, QAReport

        qa = QAReport(persona_fits=[
            PersonaFitScore(persona_id="a", persona_name="A", fit_score=5),
            PersonaFitScore(persona_id="b", persona_name="B", fit_score=9),
        ])
        assert qa.top_persona is not None
        assert qa.top_persona.persona_id == "b"

    def test_to_retry_feedback_with_diagnostics(self):
        """진단이 있으면 약점 기반 피드백 텍스트 생성."""
        from storage.models import QAAxisDiagnostic, QAReport

        qa = QAReport(
            hook_score=5, fact_score=12, tone_score=8, kick_score=5,
            angle_score=5, regulation_score=3, algorithm_score=2,
            diagnostics=[
                QAAxisDiagnostic(axis="hook", score=5, max_score=20,
                                 reason="도입이 약하다", suggestion="질문으로 시작"),
                QAAxisDiagnostic(axis="fact", score=12, max_score=15),
            ],
        )
        feedback = qa.to_retry_feedback()
        assert "hook" in feedback
        assert "질문으로 시작" in feedback
        assert "fact" not in feedback  # fact는 약점이 아님 (12/15 > 50%)

    def test_to_retry_feedback_fallback_warnings(self):
        """진단 없으면 warnings 기반 폴백."""
        from storage.models import QAReport

        qa = QAReport(warnings=["과장 수식어 사용"])
        feedback = qa.to_retry_feedback()
        assert "과장 수식어" in feedback

    def test_emoji_report_with_weak_axes_and_personas(self):
        """Pro 이모지 리포트에 약점/페르소나 표시."""
        from storage.models import PersonaFitScore, QAAxisDiagnostic, QAReport

        qa = QAReport(
            hook_score=5,
            diagnostics=[
                QAAxisDiagnostic(axis="hook", score=5, max_score=20),
            ],
            persona_fits=[
                PersonaFitScore(persona_id="ea", persona_name="얼리어답터", fit_score=7),
            ],
        )
        report = qa.to_emoji_report()
        assert "약점" in report
        assert "hook" in report
        assert "얼리어답터:7" in report

    def test_parse_pro_qa_flat_scores(self):
        """_parse_pro_qa가 flat scores 구조도 처리."""
        from generators.content_engine import _parse_pro_qa

        class FakeConfig:
            qa_min_score = 70

        data = {
            "scores": {"hook": 15, "fact": 10, "tone": 12, "kick": 10,
                       "angle": 10, "regulation": 8, "algorithm": 7,
                       "reader_value": 6, "originality": 5, "credibility": 7},
            "diagnostics": {
                "hook": {"reason": "강한 시작", "suggestion": ""},
                "fact": {"reason": "정확함", "suggestion": ""},
            },
            "persona_fits": [
                {"persona_id": "practitioner", "fit_score": 8, "reason": "실무 관련"}
            ],
            "rewrite_suggestion": "도입부를 질문으로",
            "warnings": [],
        }
        qa = _parse_pro_qa(data, FakeConfig())
        assert qa.hook_score == 15
        assert qa.total_score == 72
        assert len(qa.diagnostics) == 10  # 모든 축
        assert qa.diagnostics[0].reason == "강한 시작"
        assert len(qa.persona_fits) == 1
        assert qa.persona_fits[0].persona_id == "practitioner"
        assert qa.rewrite_suggestion == "도입부를 질문으로"

    def test_parse_pro_qa_legacy_flat(self):
        """scores 키 없이 flat한 구조도 하위호환."""
        from generators.content_engine import _parse_pro_qa

        class FakeConfig:
            qa_min_score = 70

        data = {"hook": 10, "fact": 8, "tone": 7, "kick": 6, "angle": 5,
                "regulation": 4, "algorithm": 3,
                "reader_value": 2, "originality": 1, "credibility": 0,
                "warnings": ["test"]}
        qa = _parse_pro_qa(data, FakeConfig())
        assert qa.hook_score == 10
        assert qa.total_score == 43
        assert qa.warnings == ["test"]


class TestSafeInt:
    """_safe_int LLM 응답 안전 파싱 테스트."""

    def test_normal_int(self):
        from generators.content_engine import _safe_int

        assert _safe_int(15, 20) == 15

    def test_string_int(self):
        from generators.content_engine import _safe_int

        assert _safe_int("12", 15) == 12

    def test_over_cap(self):
        from generators.content_engine import _safe_int

        assert _safe_int(25, 20) == 20

    def test_negative(self):
        from generators.content_engine import _safe_int

        assert _safe_int(-5, 10) == 0

    def test_none(self):
        from generators.content_engine import _safe_int

        assert _safe_int(None, 10) == 0

    def test_fraction_string(self):
        """LLM이 '15/20' 같은 문자열 반환 시 첫 숫자 추출."""
        from generators.content_engine import _safe_int

        assert _safe_int("15/20", 20) == 15

    def test_tilde_prefix(self):
        """LLM이 '~12' 같은 문자열 반환 시 숫자 추출."""
        from generators.content_engine import _safe_int

        assert _safe_int("~12", 15) == 12

    def test_garbage_string(self):
        """숫자 없는 문자열은 0."""
        from generators.content_engine import _safe_int

        assert _safe_int("high", 10) == 0


class TestNaverGuide:
    """네이버 가이드 검색의도 분류 테스트."""

    def test_naver_guide_has_search_intent(self):
        """네이버 가이드에 검색 의도 분류가 포함된다."""
        from prompts.content_generation import build_content_prompt

        prompt = build_content_prompt(
            platform="naver",
            project_name="테스트",
            core_message="테스트 메시지",
            target_audience="개발자",
            trend_summary="트렌드 요약",
            regulation_checklist="체크리스트",
        )
        assert "검색 의도 분류" in prompt
        assert "정보성" in prompt
        assert "비교형" in prompt
        assert "How-to" in prompt
        assert "후기형" in prompt
        assert "search_intent" in prompt

    def test_naver_guide_has_title_patterns(self):
        """네이버 가이드에 2026 제목 패턴이 포함된다."""
        from prompts.content_generation import build_content_prompt

        prompt = build_content_prompt(
            platform="naver",
            project_name="테스트",
            core_message="메시지",
            target_audience="대상",
            trend_summary="요약",
            regulation_checklist="리스트",
        )
        assert "제목 패턴" in prompt
        assert "30~45자" in prompt


class TestConfigValidation:
    """config.validate() 테스트."""

    def test_validate_notion_missing_token(self):
        """Notion 발행 활성인데 토큰 없으면 ValueError."""
        import pytest

        from config import CIEConfig

        config = CIEConfig()
        config.enable_notion_publish = True
        config.notion_token = ""
        config.notion_database_id = ""
        with pytest.raises(ValueError):
            config.validate()

    def test_validate_x_missing_token(self):
        """X 발행 활성인데 토큰 없으면 ValueError."""
        import pytest

        from config import CIEConfig

        config = CIEConfig()
        config.enable_x_publish = True
        config.x_access_token = ""
        with pytest.raises(ValueError):
            config.validate()

    def test_validate_passes_when_disabled(self):
        """발행 비활성이면 검증 통과."""
        from config import CIEConfig

        config = CIEConfig()
        config.enable_notion_publish = False
        config.enable_x_publish = False
        config.validate()  # 예외 없음


class TestXPublisher:
    @staticmethod
    def _make_content():
        from storage.models import GeneratedContent, QAReport

        return GeneratedContent(
            platform="x",
            content_type="post",
            body="테스트용 게시물 본문입니다.",
            hashtags=["ai", "automation"],
            regulation_compliant=True,
            qa_report=QAReport(
                hook_score=15,
                fact_score=12,
                tone_score=12,
                kick_score=11,
                angle_score=11,
                regulation_score=8,
                algorithm_score=9,
            ),
        )

    def test_validate_x_requires_user_context_token_message(self, capsys):
        import pytest

        from config import CIEConfig

        config = CIEConfig()
        config.enable_x_publish = True
        config.x_access_token = "   "

        with pytest.raises(ValueError) as excinfo:
            config.validate()

        captured = capsys.readouterr()
        assert "Authorization Code with PKCE" in captured.err
        assert "설정 오류" in str(excinfo.value)

    def test_publish_to_x_uses_async_httpx(self):
        from config import CIEConfig
        from storage.x_publisher import publish_to_x

        response = MagicMock()
        response.status_code = 201
        response.json.return_value = {"data": {"id": "42"}}
        response.text = ""

        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        client.post.return_value = response

        config = CIEConfig()
        config.enable_x_publish = True
        config.x_access_token = "user-context-token"

        content = self._make_content()

        with patch("storage.x_publisher.httpx.AsyncClient", return_value=client):
            result = asyncio.run(publish_to_x(content, config))

        assert result.success is True
        assert result.page_id == "42"
        assert content.publish_target == "x"
        assert content.publish_error == ""
        assert client.post.await_count == 1
        assert client.post.await_args.kwargs["headers"]["Authorization"] == "Bearer user-context-token"

    def test_publish_to_x_surfaces_api_errors(self):
        from config import CIEConfig
        from storage.x_publisher import publish_to_x

        response = MagicMock()
        response.status_code = 403
        response.json.return_value = {"title": "Forbidden"}
        response.text = '{"title":"Forbidden"}'

        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        client.post.return_value = response

        config = CIEConfig()
        config.enable_x_publish = True
        config.x_access_token = "user-context-token"

        content = self._make_content()

        with patch("storage.x_publisher.httpx.AsyncClient", return_value=client):
            result = asyncio.run(publish_to_x(content, config))

        assert result.success is False
        assert "Forbidden" in result.error
        assert content.publish_target == ""


# ═══════════════════════════════════════════════════
#  Phase 2: X 스레드 + 성과 수집
# ═══════════════════════════════════════════════════


class TestThreadPost:
    """X 스레드 모델 테스트."""

    def test_thread_post_creation(self):
        from storage.models import ThreadPost

        tp = ThreadPost(index=0, role="hook", body="첫 트윗", char_count=3)
        assert tp.role == "hook"
        assert tp.index == 0

    def test_generated_content_is_thread(self):
        from storage.models import GeneratedContent, ThreadPost

        # 스레드가 아닌 일반 콘텐츠
        normal = GeneratedContent(platform="x", content_type="post", body="test")
        assert normal.is_thread is False

        # 스레드 콘텐츠
        thread = GeneratedContent(
            platform="x", content_type="x_thread",
            thread_posts=[
                ThreadPost(index=0, role="hook", body="Hook!"),
                ThreadPost(index=1, role="body", body="본문"),
                ThreadPost(index=2, role="kick", body="Kick!"),
            ],
        )
        assert thread.is_thread is True
        assert "hook" in thread.thread_summary
        assert "kick" in thread.thread_summary

    def test_thread_summary_empty(self):
        from storage.models import GeneratedContent

        c = GeneratedContent(platform="x", content_type="post", body="short body")
        assert c.thread_summary == "short body"

    def test_x_thread_guide_exists(self):
        """x_thread 플랫폼 가이드가 존재한다."""
        from prompts.content_generation import build_content_prompt

        prompt = build_content_prompt(
            platform="x_thread",
            project_name="테스트",
            core_message="메시지",
            target_audience="대상",
            trend_summary="요약",
            regulation_checklist="리스트",
        )
        assert "Hook 트윗" in prompt
        assert "Kick 트윗" in prompt
        assert "thread_posts" in prompt


class TestPerformanceTable:
    """실측 성과 수집 테스트."""

    def test_perf_table_creation(self, tmp_path):
        """content_actual_performance 테이블이 스키마에 포함."""
        from config import CIEConfig
        from storage.local_db import get_connection

        config = CIEConfig()
        config.sqlite_path = str(tmp_path / "test_perf.db")
        conn = get_connection(config)

        # 성과 테이블 존재 확인
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        assert "content_actual_performance" in table_names
        conn.close()

    def test_calc_engagement_rate(self):
        """ER 계산이 정확한지 확인."""
        from scripts.collect_post_performance import calc_engagement_rate

        metrics = {"impressions": 1000, "likes": 50, "retweets": 10,
                   "quotes": 5, "replies": 3, "bookmarks": 12}
        er = calc_engagement_rate(metrics)
        # (50+10+5+3+12)/1000 = 80/1000 = 8%
        assert abs(er - 8.0) < 0.01

    def test_calc_engagement_rate_zero_impressions(self):
        """impression이 0이면 ER도 0."""
        from scripts.collect_post_performance import calc_engagement_rate

        assert calc_engagement_rate({"impressions": 0}) == 0.0
