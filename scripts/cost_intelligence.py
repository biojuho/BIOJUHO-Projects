"""
Cost Intelligence - LLM 비용 분석, 예측, 최적화 제안 엔진.

shared/llm/data/llm_costs.db 데이터를 기반으로:
  - 프로젝트별/모델별/일별 비용 분석
  - 비용 트렌드 및 예산 초과 예측
  - 모델 다운그레이드 제안 (품질 유지 범위 내)
  - 시간대별 비용 패턴 분석

Usage::
    analyzer = CostAnalyzer()
    report = analyzer.generate_report(days=30)
    print(report.to_markdown())
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
LLM_DB_PATH = WORKSPACE / "shared" / "llm" / "data" / "llm_costs.db"

# 모델별 대체 후보 (비용 낮은 순)
MODEL_ALTERNATIVES = {
    "claude-sonnet-4-6": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "claude-haiku-4-5-20251001"],
    "claude-opus-4-6": ["claude-sonnet-4-6", "gemini-2.5-pro-preview-03-25"],
    "gemini-2.5-pro-preview-03-25": ["gemini-2.5-flash", "gemini-2.5-flash-lite"],
    "gemini-2.5-flash": ["gemini-2.5-flash-lite"],
    "gpt-4o": ["gpt-4o-mini", "gemini-2.5-flash-lite"],
}


@dataclass
class ModelUsage:
    model: str
    calls: int = 0
    total_cost: float = 0.0
    avg_input_tokens: float = 0.0
    avg_output_tokens: float = 0.0
    error_rate: float = 0.0


@dataclass
class ProjectUsage:
    project: str
    calls: int = 0
    total_cost: float = 0.0
    top_model: str = ""
    percentage: float = 0.0


@dataclass
class DailyUsage:
    date: str
    calls: int = 0
    cost: float = 0.0
    errors: int = 0


@dataclass
class OptimizationSuggestion:
    category: str  # "model_downgrade", "time_shift", "cache_improvement"
    description: str
    estimated_saving: float = 0.0
    priority: str = "medium"  # low, medium, high


@dataclass
class CostReport:
    period_days: int = 30
    total_cost: float = 0.0
    total_calls: int = 0
    total_errors: int = 0
    daily_average: float = 0.0
    by_project: list[ProjectUsage] = field(default_factory=list)
    by_model: list[ModelUsage] = field(default_factory=list)
    daily_trend: list[DailyUsage] = field(default_factory=list)
    suggestions: list[OptimizationSuggestion] = field(default_factory=list)
    budget_forecast: dict = field(default_factory=dict)

    def to_markdown(self) -> str:
        lines = [
            f"## LLM 비용 리포트 (최근 {self.period_days}일)",
            "",
            "### 요약",
            f"- 총 비용: ${self.total_cost:.4f}",
            f"- 총 호출: {self.total_calls}회",
            f"- 총 에러: {self.total_errors}회 ({self._error_rate():.1f}%)",
            f"- 일 평균: ${self.daily_average:.4f}",
            "",
        ]

        if self.by_project:
            lines.append("### 프로젝트별")
            lines.append("| 프로젝트 | 호출 | 비용 | 비중 |")
            lines.append("|----------|------|------|------|")
            for p in self.by_project:
                lines.append(f"| {p.project} | {p.calls} | ${p.total_cost:.4f} | {p.percentage:.1f}% |")
            lines.append("")

        if self.by_model:
            lines.append("### 모델별")
            lines.append("| 모델 | 호출 | 비용 | 평균 입력 | 평균 출력 | 에러율 |")
            lines.append("|------|------|------|----------|----------|--------|")
            for m in self.by_model:
                lines.append(
                    f"| {m.model} | {m.calls} | ${m.total_cost:.4f} "
                    f"| {m.avg_input_tokens:.0f} | {m.avg_output_tokens:.0f} "
                    f"| {m.error_rate:.1f}% |"
                )
            lines.append("")

        if self.daily_trend:
            lines.append("### 최근 7일 추이")
            for d in self.daily_trend[:7]:
                bar_len = min(int(d.cost / max(self.daily_average, 0.001) * 5), 20)
                bar = "#" * max(bar_len, 1)
                lines.append(f"  {d.date}: ${d.cost:.4f} ({d.calls}회) {bar}")
            lines.append("")

        if self.budget_forecast:
            lines.append("### 예산 예측")
            lines.append(f"- 월 예상 비용: ${self.budget_forecast.get('monthly_estimate', 0):.2f}")
            lines.append(f"- 추세: {self.budget_forecast.get('trend', 'stable')}")
            lines.append("")

        if self.suggestions:
            lines.append("### 최적화 제안")
            for i, s in enumerate(self.suggestions, 1):
                saving = f" (예상 절감: ${s.estimated_saving:.4f}/일)" if s.estimated_saving > 0 else ""
                priority_icon = {"high": "[!]", "medium": "[*]", "low": "[-]"}.get(s.priority, "[-]")
                lines.append(f"{i}. {priority_icon} **{s.category}**: {s.description}{saving}")
            lines.append("")

        return "\n".join(lines)

    def _error_rate(self) -> float:
        return (self.total_errors / self.total_calls * 100) if self.total_calls > 0 else 0.0


class CostAnalyzer:
    """LLM 비용 데이터 분석기."""

    def __init__(self, db_path: Path = LLM_DB_PATH):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection | None:
        if not self.db_path.exists():
            return None
        return sqlite3.connect(str(self.db_path))

    def generate_report(self, days: int = 30) -> CostReport:
        """종합 비용 리포트 생성."""
        conn = self._connect()
        if conn is None:
            return CostReport(period_days=days)

        try:
            report = CostReport(period_days=days)

            # 전체 요약
            row = conn.execute(
                """SELECT COUNT(*), SUM(cost_usd),
                          SUM(CASE WHEN success=0 THEN 1 ELSE 0 END)
                   FROM llm_calls WHERE timestamp >= datetime('now', ?)""",
                (f"-{days} days",),
            ).fetchone()
            report.total_calls = row[0] or 0
            report.total_cost = round(row[1] or 0.0, 6)
            report.total_errors = row[2] or 0
            report.daily_average = round(report.total_cost / max(days, 1), 6)

            # 프로젝트별
            report.by_project = self._by_project(conn, days, report.total_cost)
            # 모델별
            report.by_model = self._by_model(conn, days)
            # 일별 추이
            report.daily_trend = self._daily_trend(conn, days)
            # 예산 예측
            report.budget_forecast = self._forecast(report.daily_trend)
            # 최적화 제안
            report.suggestions = self._generate_suggestions(report)

            return report
        finally:
            conn.close()

    def _by_project(self, conn: sqlite3.Connection, days: int, total: float) -> list[ProjectUsage]:
        rows = conn.execute(
            """SELECT project, COUNT(*), SUM(cost_usd),
                      (SELECT model FROM llm_calls AS sub
                       WHERE sub.project = llm_calls.project
                         AND sub.timestamp >= datetime('now', ?)
                       GROUP BY model ORDER BY COUNT(*) DESC LIMIT 1) as top_model
               FROM llm_calls
               WHERE timestamp >= datetime('now', ?)
               GROUP BY project ORDER BY SUM(cost_usd) DESC""",
            (f"-{days} days", f"-{days} days"),
        ).fetchall()

        result = []
        for r in rows:
            cost = round(r[2] or 0.0, 6)
            result.append(ProjectUsage(
                project=r[0] or "unknown",
                calls=r[1],
                total_cost=cost,
                top_model=r[3] or "",
                percentage=round(cost / total * 100, 1) if total > 0 else 0,
            ))
        return result

    def _by_model(self, conn: sqlite3.Connection, days: int) -> list[ModelUsage]:
        rows = conn.execute(
            """SELECT model, COUNT(*), SUM(cost_usd),
                      AVG(input_tokens), AVG(output_tokens),
                      SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
               FROM llm_calls
               WHERE timestamp >= datetime('now', ?)
               GROUP BY model ORDER BY SUM(cost_usd) DESC""",
            (f"-{days} days",),
        ).fetchall()

        return [
            ModelUsage(
                model=r[0],
                calls=r[1],
                total_cost=round(r[2] or 0.0, 6),
                avg_input_tokens=r[3] or 0,
                avg_output_tokens=r[4] or 0,
                error_rate=round(r[5] or 0.0, 1),
            )
            for r in rows
        ]

    def _daily_trend(self, conn: sqlite3.Connection, days: int) -> list[DailyUsage]:
        rows = conn.execute(
            """SELECT DATE(timestamp), COUNT(*), SUM(cost_usd),
                      SUM(CASE WHEN success=0 THEN 1 ELSE 0 END)
               FROM llm_calls
               WHERE timestamp >= datetime('now', ?)
               GROUP BY DATE(timestamp) ORDER BY DATE(timestamp) DESC""",
            (f"-{days} days",),
        ).fetchall()

        return [
            DailyUsage(date=r[0], calls=r[1], cost=round(r[2] or 0.0, 6), errors=r[3] or 0)
            for r in rows
        ]

    def _forecast(self, daily: list[DailyUsage]) -> dict:
        if len(daily) < 3:
            return {"monthly_estimate": 0, "trend": "insufficient_data"}

        recent_7 = [d.cost for d in daily[:7]]
        older_7 = [d.cost for d in daily[7:14]] if len(daily) >= 14 else recent_7

        avg_recent = sum(recent_7) / len(recent_7) if recent_7 else 0
        avg_older = sum(older_7) / len(older_7) if older_7 else avg_recent

        if avg_older > 0:
            change_pct = (avg_recent - avg_older) / avg_older * 100
        else:
            change_pct = 0

        if change_pct > 15:
            trend = "increasing"
        elif change_pct < -15:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "monthly_estimate": round(avg_recent * 30, 2),
            "trend": trend,
            "weekly_avg": round(avg_recent * 7, 4),
            "change_pct": round(change_pct, 1),
        }

    def _generate_suggestions(self, report: CostReport) -> list[OptimizationSuggestion]:
        suggestions = []

        # 1. 고비용 모델 다운그레이드 제안
        for m in report.by_model:
            if m.model in MODEL_ALTERNATIVES and m.total_cost > 0.01:
                alts = MODEL_ALTERNATIVES[m.model]
                suggestions.append(OptimizationSuggestion(
                    category="모델 다운그레이드",
                    description=(
                        f"{m.model} ({m.calls}회, ${m.total_cost:.4f}) -> "
                        f"{alts[0]} 전환 검토"
                    ),
                    estimated_saving=m.total_cost * 0.5 / max(report.period_days, 1),
                    priority="high" if m.total_cost > 0.5 else "medium",
                ))

        # 2. 에러율 높은 모델
        for m in report.by_model:
            if m.error_rate > 10 and m.calls > 10:
                suggestions.append(OptimizationSuggestion(
                    category="에러율 개선",
                    description=f"{m.model} 에러율 {m.error_rate:.1f}% - 재시도 비용 낭비 가능",
                    priority="high",
                ))

        # 3. 예산 초과 예측
        forecast = report.budget_forecast
        if forecast.get("trend") == "increasing" and forecast.get("change_pct", 0) > 20:
            suggestions.append(OptimizationSuggestion(
                category="비용 증가 경고",
                description=(
                    f"주간 비용 {forecast['change_pct']:.0f}% 증가 추세. "
                    f"월 예상: ${forecast['monthly_estimate']:.2f}"
                ),
                priority="high",
            ))

        # 4. 캐시 활용도
        if report.total_calls > 100 and report.daily_average > 0.5:
            suggestions.append(OptimizationSuggestion(
                category="캐시 최적화",
                description="일 평균 호출이 많음. 스코어 캐시 TTL 확대 또는 결과 메모이제이션 검토",
                estimated_saving=report.daily_average * 0.1,
                priority="medium",
            ))

        return sorted(suggestions, key=lambda s: {"high": 0, "medium": 1, "low": 2}[s.priority])


def main():
    """CLI 엔트리포인트."""
    import argparse

    parser = argparse.ArgumentParser(description="LLM Cost Intelligence Report")
    parser.add_argument("--days", type=int, default=30, help="분석 기간 (일)")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    args = parser.parse_args()

    analyzer = CostAnalyzer()
    report = analyzer.generate_report(days=args.days)

    if args.json:
        import json
        print(json.dumps({
            "total_cost": report.total_cost,
            "total_calls": report.total_calls,
            "daily_average": report.daily_average,
            "forecast": report.budget_forecast,
            "suggestions": [
                {"category": s.category, "description": s.description,
                 "saving": s.estimated_saving, "priority": s.priority}
                for s in report.suggestions
            ],
        }, ensure_ascii=False, indent=2))
    else:
        print(report.to_markdown())


if __name__ == "__main__":
    main()
