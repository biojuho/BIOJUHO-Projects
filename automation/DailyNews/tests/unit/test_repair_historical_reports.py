from __future__ import annotations

from pathlib import Path

import automation.DailyNews.scripts.repair_historical_reports as repair
from antigravity_mcp.domain.models import ChannelDraft, ContentItem, ContentReport, GeneratedPayload
from antigravity_mcp.state.store import PipelineStateStore


def _make_suspicious_report(*, category: str, created_at: str) -> ContentReport:
    return ContentReport(
        report_id=f"report-{category.lower()}-test",
        category=category,
        window_name="morning",
        window_start="2026-04-09T00:00:00+00:00",
        window_end="2026-04-09T12:00:00+00:00",
        summary_lines=[
            f"{category} morning brief covers 3 curated items.",
            "Top signals: Story A; Story B; Story C.",
            "Most active sources: Reuters (3).",
        ],
        insights=[
            f"{category} coverage is clustering around Story A.",
            "Operators should review 3 candidate stories before publishing.",
        ],
        channel_drafts=[
            ChannelDraft(
                channel="x",
                status="draft",
                content="Fallback draft",
                source="fallback",
                is_fallback=True,
            )
        ],
        source_links=["https://example.com/story-a"],
        status="draft",
        fingerprint=f"fp-{category.lower()}",
        created_at=created_at,
        updated_at=created_at,
        generation_mode="v1-brief",
        quality_state="fallback",
        analysis_meta={
            "parser": {
                "used_fallback": True,
                "format": "fallback",
                "reason": "v1_parse_failure",
                "provider": "shared.llm",
                "model_name": "gpt-4o-mini",
            },
            "auto_heal": {"applied": True},
        },
    )


def test_find_best_candidate_accepts_nearby_contentful_restore_even_with_one_extra_violation():
    report = _make_suspicious_report(category="Crypto", created_at="2026-04-09T09:04:38.293411+00:00")
    items = [
        ContentItem(
            source_name="Reuters",
            category="Crypto",
            title="Story A",
            link="https://example.com/story-a",
            summary="Summary A",
        )
    ]
    rows = [
        {
            "prompt_hash": "prompt-hash-1",
            "created_at": "2026-04-09T09:04:29.250158+00:00",
            "model_name": "gemini-2.5-flash-lite",
            "response_text": """## Summary
* 이란, 호르무즈 해협 통행료로 비트코인 결제 허용하며 제재 회피 강화.
* 미국 소비자물가 지표 발표 앞두고도 비트코인 시장은 자체 흐름 유지.
* 글로벌 결제 시장에서 암호화폐 활용 전망, 비자/마스터카드 등 주도적 움직임.
## Insights
* 지정학적 리스크와 규제 환경 변화가 암호화폐 시장의 새로운 동인으로 작용하고 있습니다.
* 기존 금융 인프라의 암호화폐 수용 움직임은 잠재적인 시장 규모 확대를 시사합니다.
## Brief
오늘의 핫 이슈: Crypto. 이란의 비트코인 결제 허용, 거시 이벤트와의 디커플링, 글로벌 결제사들의 암호화폐 수용이 동시에 겹치며 시장 구조 변화가 진행되고 있습니다.
이 움직임은 단순한 가격 변동이 아니라 결제 인프라와 지정학 리스크가 만나는 접점에서 암호화폐의 역할이 커지고 있다는 신호입니다.
시장 참여자들은 규제와 실사용 확대가 충돌하는 지점을 관찰해야 하며, 전통 금융권의 수용 속도에 따라 올해 하반기 구조적 재평가가 이어질 수 있습니다.
## Draft
Crypto draft""",
        }
    ]

    candidate = repair._find_best_candidate(report=report, items=items, rows=rows)

    assert candidate is not None
    assert candidate.repair_mode == "partial"
    assert len(candidate.violations) == 2


def test_repair_report_marks_cache_restore_provenance(tmp_path, monkeypatch):
    store = PipelineStateStore(path=tmp_path / "pipeline_state.db")
    report = _make_suspicious_report(category="Tech", created_at="2026-04-08T22:03:17.216648+00:00")
    store.save_report(report)
    monkeypatch.setattr(repair, "BACKUP_DIR", tmp_path / "repair_backups")

    candidate = repair.CandidateMatch(
        prompt_hash="prompt-hash-2",
        created_at="2026-04-08T22:03:17.213130+00:00",
        model_name="claude-haiku-4-5",
        payload=GeneratedPayload(
            summary_lines=[
                "First summary line [A1]",
                "Second summary line [A2]",
                "Third summary line [A3]",
            ],
            insights=[
                "First insight line [A1]",
                "Second insight line [A2]",
            ],
            channel_drafts=[ChannelDraft(channel="x", status="draft", content="Recovered draft")],
            generation_mode="v1-brief",
            parse_meta={
                "used_fallback": False,
                "format": "v1",
                "brief_body": "Recovered brief body",
            },
        ),
        warnings=[],
        violations=[],
        citation_count=2,
        distance_seconds=0.0,
        repair_mode="strict",
    )

    backup_path = repair._repair_report(store=store, report=report, candidate=candidate)
    restored = store.get_report(report.report_id)

    assert backup_path == tmp_path / "repair_backups" / f"{report.report_id}.before-cache-repair.json"
    assert backup_path.exists()
    assert restored is not None
    assert restored.analysis_meta["parser"]["provider"] == "sqlite-cache"
    assert restored.analysis_meta["parser"]["upstream_provider"] == "shared.llm"
    assert restored.analysis_meta["manual_repair"]["source_provider_before_restore"] == "shared.llm"
    assert restored.analysis_meta["manual_repair"]["source_model_before_restore"] == "gpt-4o-mini"

    store.close()
