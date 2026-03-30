"""CIE 데이터 모델 v2.0 — 트렌드, 규제, 콘텐츠, QA 리포트, 발행."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# ═══════════════════════════════════════════════════════
#  1단계: 트렌드 수집
# ═══════════════════════════════════════════════════════


@dataclass
class PlatformTrend:
    """개별 플랫폼 트렌드 항목."""

    keyword: str
    hashtags: list[str] = field(default_factory=list)
    volume: int = 0
    format_trend: str = ""  # 인기 포맷 (캐러셀, 쓰레드, 숏폼 등)
    tone_trend: str = ""  # 톤 경향 (유머, 진정성, 논쟁 등)
    project_connection: str = ""  # 프로젝트 접점 분석
    # v2.0: GDT Bridge 확장 필드
    sentiment: str = "neutral"  # positive / negative / neutral
    confidence: int = 0  # cross_source_confidence (0~100)
    hook_starter: str = ""  # 추천 Hook 문장
    optimal_post_hour: int = -1  # 최적 게시 시간 (-1 = 미설정)


@dataclass
class PlatformTrendReport:
    """플랫폼별 트렌드 리포트."""

    platform: str  # "x" | "threads" | "naver"
    trends: list[PlatformTrend] = field(default_factory=list)
    key_insights: list[str] = field(default_factory=list)
    collected_at: datetime = field(default_factory=datetime.now)
    raw_response: str = ""  # LLM 원본 응답 (디버깅용)


@dataclass
class MergedTrendReport:
    """모든 플랫폼의 트렌드를 통합한 리포트."""

    platform_reports: list[PlatformTrendReport] = field(default_factory=list)
    cross_platform_keywords: list[str] = field(default_factory=list)
    top_insights: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_summary_text(self) -> str:
        """프롬프트 컨텍스트 주입용 요약 텍스트."""
        lines = []
        for report in self.platform_reports:
            lines.append(f"\n■ {report.platform.upper()} 트렌드:")
            for t in report.trends:
                tags = ", ".join(t.hashtags) if t.hashtags else "(없음)"
                lines.append(f"  - {t.keyword} (볼륨:{t.volume}) | " f"포맷:{t.format_trend} | 톤:{t.tone_trend}")
                if t.sentiment != "neutral":
                    lines.append(f"    ↳ 감성: {t.sentiment} | 신뢰도: {t.confidence}%")
                if t.hook_starter:
                    lines.append(f"    ↳ 추천 Hook: {t.hook_starter}")
                if t.project_connection:
                    lines.append(f"    → 프로젝트 접점: {t.project_connection}")
        if self.top_insights:
            lines.append("\n■ 핵심 인사이트:")
            for ins in self.top_insights:
                lines.append(f"  • {ins}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════
#  2단계: 규제 점검
# ═══════════════════════════════════════════════════════


@dataclass
class RegulationReport:
    """플랫폼별 규제 점검 리포트."""

    platform: str
    policy_changes: list[dict] = field(default_factory=list)
    penalty_triggers: list[str] = field(default_factory=list)
    algorithm_preferences: list[str] = field(default_factory=list)
    do_list: list[str] = field(default_factory=list)
    dont_list: list[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.now)
    raw_response: str = ""


@dataclass
class UnifiedChecklist:
    """3개 플랫폼 통합 Do & Don't 체크리스트."""

    do_items: list[dict] = field(default_factory=list)  # {platform, action, priority}
    dont_items: list[dict] = field(default_factory=list)  # {platform, action, severity}
    summary: str = ""

    def to_checklist_text(self) -> str:
        """프롬프트 컨텍스트 주입용 체크리스트 텍스트."""
        lines = ["[통합 Do & Don't 체크리스트]"]
        lines.append("\n✅ DO (반드시 해라):")
        for item in self.do_items:
            lines.append(f"  [{item.get('platform', '공통')}] {item.get('action', '')}")
        lines.append("\n❌ DON'T (절대 하지 마라):")
        for item in self.dont_items:
            sev = item.get("severity", "중")
            lines.append(f"  [{item.get('platform', '공통')}] " f"[{sev}] {item.get('action', '')}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════
#  3단계: 콘텐츠 생성
# ═══════════════════════════════════════════════════════


@dataclass
class QAReport:
    """7축 품질 검증 리포트."""

    hook_score: int = 0  # 0~20 첫 문장 주목도
    fact_score: int = 0  # 0~15 사실 일관성
    tone_score: int = 0  # 0~15 톤 일관성
    kick_score: int = 0  # 0~15 결론/펀치라인
    angle_score: int = 0  # 0~15 고유 관점
    regulation_score: int = 0  # 0~10 규제 준수
    algorithm_score: int = 0  # 0~10 알고리즘 최적화
    warnings: list[str] = field(default_factory=list)

    @property
    def total_score(self) -> int:
        return (
            self.hook_score
            + self.fact_score
            + self.tone_score
            + self.kick_score
            + self.angle_score
            + self.regulation_score
            + self.algorithm_score
        )

    @property
    def pass_threshold(self) -> bool:
        return self.total_score >= 70

    def to_emoji_report(self) -> str:
        """이모지 기반 요약 리포트."""
        checks = [
            f"Hook: {self.hook_score}/20",
            f"Fact: {self.fact_score}/15",
            f"Tone: {self.tone_score}/15",
            f"Kick: {self.kick_score}/15",
            f"Angle: {self.angle_score}/15",
            f"Reg: {self.regulation_score}/10",
            f"Algo: {self.algorithm_score}/10",
        ]
        status = "✅ PASS" if self.pass_threshold else "❌ FAIL"
        return f"{status} ({self.total_score}/100) | " + " | ".join(checks)


@dataclass
class GeneratedContent:
    """생성된 플랫폼별 콘텐츠."""

    platform: str  # "x" | "threads" | "naver"
    content_type: str  # "post" | "thread" | "blog"
    title: str = ""  # 네이버 블로그 제목
    body: str = ""
    hashtags: list[str] = field(default_factory=list)
    trend_keywords_used: list[str] = field(default_factory=list)
    qa_report: QAReport | None = None
    regulation_compliant: bool = False
    algorithm_optimized: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    # v2.0: 발행 메타데이터
    published_at: datetime | None = None
    publish_target: str = ""  # "notion" | "x" | "naver" | "" (미발행)
    notion_page_id: str = ""  # Notion 페이지 ID
    publish_error: str = ""  # 발행 실패 시 에러 메시지

    @property
    def qa_passed(self) -> bool:
        if self.qa_report is None:
            return False
        return self.qa_report.pass_threshold

    @property
    def is_published(self) -> bool:
        return self.published_at is not None


@dataclass
class PublishResult:
    """발행 결과."""

    platform: str
    success: bool
    target: str  # "notion" | "x"
    page_id: str = ""  # Notion page ID
    error: str = ""
    published_at: datetime = field(default_factory=datetime.now)


@dataclass
class ContentBatch:
    """하나의 파이프라인 실행에서 생성된 콘텐츠 묶음."""

    contents: list[GeneratedContent] = field(default_factory=list)
    trend_report: MergedTrendReport | None = None
    checklist: UnifiedChecklist | None = None
    created_at: datetime = field(default_factory=datetime.now)
    # v2.0: 발행 결과
    publish_results: list[PublishResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.qa_passed for c in self.contents if c.qa_report)

    def summary(self) -> str:
        platforms = {c.platform for c in self.contents}
        scores = [c.qa_report.total_score for c in self.contents if c.qa_report]
        avg = sum(scores) / len(scores) if scores else 0
        published = sum(1 for c in self.contents if c.is_published)
        pub_str = f" | 발행: {published}건" if published else ""
        return (
            f"콘텐츠 {len(self.contents)}건 | "
            f"플랫폼: {', '.join(sorted(platforms))} | "
            f"평균 QA: {avg:.0f}/100{pub_str}"
        )


# ═══════════════════════════════════════════════════════
#  보너스: 월간 회고
# ═══════════════════════════════════════════════════════


@dataclass
class MonthlyReview:
    """월간 회고 리포트."""

    month: str  # YYYY-MM
    top_performers: list[dict] = field(default_factory=list)
    bottom_performers: list[dict] = field(default_factory=list)
    regulation_issues: list[str] = field(default_factory=list)
    next_month_strategy: list[str] = field(default_factory=list)
    system_improvements: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
