"""
A/B Test v2.0: Audience-First Economy_KR Pipeline Validation

Changes from v1:
- ✅ Audience profile definition BEFORE running test
- ✅ KPI-based comparison (not just subjective)
- ✅ Structured output for metrics tracking
- ✅ Hypothesis validation framework
- ✅ Recommendations based on data
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
WORKSPACE_ROOT = SCRIPT_PATH.parents[3]

for candidate in (
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "scripts",
    WORKSPACE_ROOT / "packages",
):
    candidate_str = str(candidate)
    if candidate.exists() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

logging.basicConfig(level=logging.INFO, format="%(message)s")

from antigravity_mcp.config import get_settings
from antigravity_mcp.integrations.brain_adapter import BrainAdapter
from antigravity_mcp.pipelines.collect import collect_content_items
from antigravity_mcp.state.store import PipelineStateStore

# ============================================================================
# AUDIENCE PROFILE (Audience-First v2.0)
# ============================================================================

AUDIENCE_PROFILE = {
    "type": "B2C",
    "target_persona": {
        "primary": "한국 개인 투자자 (2040세대)",
        "demographics": {
            "age": "25-45세",
            "occupation": ["직장인", "소상공인", "1인 창업자"],
            "tech_level": "중상 (Notion, X 일상적 사용)",
        },
        "psychographics": {
            "pain_points": [
                "부동산/주식 시장 불확실성에 대한 불안",
                "경제 뉴스가 너무 많고 복잡함",
                "실생활과 무관한 뉴스 피로감",
            ],
            "goals": [
                "아침 5분 안에 핵심 경제 동향 파악",
                "투자/재테크 의사결정에 도움 되는 인사이트",
                "공유 가치 있는 콘텐츠 (지인에게 보여줄 만한)",
            ],
            "emotional_triggers": ["FOMO (놓칠까 두려움)", "경제적 안전", "정보 우위"],
        },
    },
    "consumption_context": {
        "channel": "X (Twitter)",
        "format": "Longform 포스트 (280자 초과)",
        "time": "평일 오전 7-9시, 점심 12-1시",
        "device": "모바일 > 데스크톱",
        "attention_span": "첫 2줄에서 결정 (3초 룰)",
    },
    "success_criteria": {
        "must_have": [
            "헤드라인이 구체적 (숫자/사실 포함)",
            "개인에게 미치는 영향 명시",
            "행동 가능한 인사이트 (또는 명확한 CTA)",
        ],
        "nice_to_have": [
            "데이터 시각화 (향후)",
            "관련 기사 링크",
            "요약 + 심화 레이어 (접기/펼치기)",
        ],
    },
    "language_culture": {
        "locale": "ko-KR",
        "tone": "전문적이되 접근 가능 (완곡 표현, 존댓말 기본)",
        "taboo": ["과도한 공포 유발", "정치 편향 명시", "투자 권유 (법적 리스크)"],
    },
}


# ============================================================================
# HYPOTHESIS & KPI (A/B Test Framework)
# ============================================================================

AB_TEST_HYPOTHESIS = {
    "hypothesis": "새 3-Stage 파이프라인은 기존 대비 더 구체적이고 실용적인 인사이트를 제공하여 독자 인게이지먼트를 높일 것",
    "version_a": {
        "name": "OLD (기존 파이프라인)",
        "description": "단일 프롬프트 요약 → X 포스트 생성",
    },
    "version_b": {
        "name": "NEW (3-Stage: Collect → Filter → Deep Analysis)",
        "description": "본문 스크래핑 → 편집 필터 → 심층 분석 + 독자 의미 명시",
    },
    "kpis": {
        "primary": {
            "name": "predicted_engagement_score",
            "description": "예상 인게이지먼트 점수 (0-100)",
            "calculation": "구체성(30점) + 실용성(30점) + 감정 공감(20점) + CTA 명확성(20점)",
            "target": "NEW가 OLD 대비 +15점 이상",
        },
        "secondary": [
            {
                "name": "content_length",
                "description": "콘텐츠 길이 (chars)",
                "target": "400-800자 (모바일 최적)",
            },
            {
                "name": "specificity_score",
                "description": "구체성 (숫자/사실 포함 여부)",
                "target": "최소 2개 이상 구체적 데이터 포인트",
            },
            {
                "name": "actionability",
                "description": "행동 가능한 인사이트 포함 여부",
                "target": "명시적 CTA or 실생활 적용 가이드",
            },
        ],
    },
    "sample_size": "최소 10개 기사 → 2개 버전 생성",
    "decision_rule": "Primary KPI +15점 이상 AND Secondary 2개 이상 충족 → NEW 채택",
}


# ============================================================================
# EVALUATION FUNCTIONS
# ============================================================================


def evaluate_content_quality(content: str, version_name: str) -> dict:
    """
    콘텐츠 품질 평가 (Audience-First 기준)
    """
    # 1. Content Length
    length = len(content)
    length_score = 100 if 400 <= length <= 800 else max(0, 100 - abs(length - 600) / 10)

    # 2. Specificity (숫자/구체적 사실 포함)
    import re

    numbers = re.findall(r"\d+[조억만천백]?\s?[원%배달러]", content)
    specificity_score = min(100, len(numbers) * 30)  # 숫자 1개당 30점, 최대 100

    # 3. Actionability (행동 유도/실용적 조언)
    action_keywords = [
        "해야",
        "필요",
        "주목",
        "확인",
        "대비",
        "준비",
        "투자",
        "관심",
        "고려",
        "체크",
        "CTA",
        "행동",
    ]
    action_count = sum(1 for kw in action_keywords if kw in content)
    actionability_score = min(100, action_count * 25)

    # 4. Emotional Resonance (감정 공감 키워드)
    emotion_keywords = [
        "위험",
        "불안",
        "기회",
        "희망",
        "위기",
        "성장",
        "도전",
        "두려움",
        "안전",
        "안심",
    ]
    emotion_count = sum(1 for kw in emotion_keywords if kw in content)
    emotion_score = min(100, emotion_count * 20)

    # 5. CTA Clarity (명확한 Next Step)
    cta_phrases = ["지금", "오늘", "이번 주", "당장", "반드시", "꼭"]
    has_clear_cta = any(phrase in content for phrase in cta_phrases)
    cta_score = 100 if has_clear_cta else 30

    # Weighted Primary KPI
    primary_kpi = specificity_score * 0.3 + actionability_score * 0.3 + emotion_score * 0.2 + cta_score * 0.2

    return {
        "version": version_name,
        "primary_kpi": round(primary_kpi, 1),
        "breakdown": {
            "length": {"value": length, "score": round(length_score, 1)},
            "specificity": {"count": len(numbers), "score": round(specificity_score, 1)},
            "actionability": {
                "count": action_count,
                "score": round(actionability_score, 1),
            },
            "emotion": {"count": emotion_count, "score": round(emotion_score, 1)},
            "cta_clarity": {"has_cta": has_clear_cta, "score": cta_score},
        },
        "passes_criteria": {
            "length_optimal": 400 <= length <= 800,
            "min_specificity": len(numbers) >= 2,
            "has_actionability": action_count >= 2,
            "has_cta": has_clear_cta,
        },
    }


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================


async def run_ab_test() -> int:
    settings = get_settings()
    state_store = PipelineStateStore(settings.pipeline_state_db)
    run_label = datetime.now().strftime("%Y-%m-%d")

    print("=" * 80)
    print("Economy_KR A/B Test v2.0 — Audience-First Validation")
    print("=" * 80)

    # Step 1: Show Audience Profile
    print("\n" + "=" * 80)
    print("🎯 AUDIENCE PROFILE")
    print("=" * 80)
    print(f"타입: {AUDIENCE_PROFILE['type']}")
    print(f"타깃: {AUDIENCE_PROFILE['target_persona']['primary']}")
    print(f"Pain Points: {', '.join(AUDIENCE_PROFILE['target_persona']['psychographics']['pain_points'][:2])}")
    print(f"채널: {AUDIENCE_PROFILE['consumption_context']['channel']}")
    print(f"성공 기준: {AUDIENCE_PROFILE['success_criteria']['must_have'][0]}")

    # Step 2: Show Hypothesis
    print("\n" + "=" * 80)
    print("🧪 A/B TEST HYPOTHESIS")
    print("=" * 80)
    print(f"가설: {AB_TEST_HYPOTHESIS['hypothesis']}")
    print(f"\nVersion A: {AB_TEST_HYPOTHESIS['version_a']['name']} — {AB_TEST_HYPOTHESIS['version_a']['description']}")
    print(f"Version B: {AB_TEST_HYPOTHESIS['version_b']['name']} — {AB_TEST_HYPOTHESIS['version_b']['description']}")
    print(
        f"\nPrimary KPI: {AB_TEST_HYPOTHESIS['kpis']['primary']['name']} (Target: {AB_TEST_HYPOTHESIS['kpis']['primary']['target']})"
    )
    print(f"Decision Rule: {AB_TEST_HYPOTHESIS['decision_rule']}")

    # Step 3: Collect Articles (NEW Version)
    print("\n" + "=" * 80)
    print("[VERSION B] NEW 3-Stage Pipeline")
    print("=" * 80)
    print("\n[Stage 1] Deep Collect - Economy_KR")
    print("-" * 40)

    items, warnings = await collect_content_items(
        categories=["Economy_KR"],
        window_name="evening",
        max_items=10,
        state_store=state_store,
        fetch_bodies=True,
    )

    if not items:
        print("WARNING: No items collected with evening window, trying 24h window")
        items, warnings = await collect_content_items(
            categories=["Economy_KR"],
            window_name="24h",
            max_items=10,
            state_store=state_store,
            fetch_bodies=True,
        )

    print(f"  Collected: {len(items)} articles")
    for item in items[:5]:  # Show first 5
        body_len = len(item.full_text) if item.full_text else 0
        print(f"  - [{item.source_name}] {item.title[:50]}... (body: {body_len} chars)")

    if not items:
        print("[ERROR] No articles collected. Check RSS feeds.")
        return 1

    # Prepare articles dict
    articles = []
    for item in items:
        articles.append(
            {
                "title": item.title,
                "description": item.summary,
                "summary": item.summary,
                "full_text": item.full_text,
                "source_name": item.source_name,
                "link": item.link,
            }
        )

    brain = BrainAdapter()
    if not brain.is_available():
        print("[ERROR] BrainAdapter not available (LLM client missing)")
        return 1

    # Stage 2 + 3: Editorial Filter + Deep Analysis
    print("\n[Stage 2+3] Editorial Filter + Deep Analysis")
    print("-" * 40)
    result_new = await brain.analyze_news(
        category="Economy_KR",
        articles=articles,
        time_window=f"{run_label} weekly_ab_test",
    )

    if not result_new:
        print("[ERROR] Brain analysis returned None")
        return 1

    new_post = result_new.get("x_thread", [""])[0].replace("\\n", "\n")
    print(f"✅ NEW 버전 생성 완료 ({len(new_post)} chars)")

    # Step 4: Load OLD Version (from hardcoded baseline)
    print("\n" + "=" * 80)
    print("[VERSION A] OLD Pipeline (Baseline)")
    print("=" * 80)
    old_post = """한국 경제, 4223조 원의 부동산 그림자가 드리우고 있습니다. 명목 GDP의 1.6배에 달하는 이 막대한 위험 노출액은 단순히 부동산 시장만의 문제가 아닙니다. 주택담보대출 둔화와 건설 경기 부진이 겹치며 그 위험은 더욱 깊어지고 있습니다.

이는 소비와 투자 심리를 위축시켜 경제 전반의 성장 동력을 약화시킬 수 있습니다. 벤처·스타트업 지원 강화나 수출 기업 보호와 같은 정책적 대응의 시급성이 더욱 커지는 이유입니다.

하지만 희망적인 신호도 있습니다. 강원도의 수출 기업 지원 노력이나 벤처·스타트업 성장 포럼 논의는 경제의 다각화와 신성장 동력 발굴이라는 긍정적인 움직임을 보여줍니다.

물론, 이러한 긍정적인 노력에도 불구하고 부동산 PF 부실 위험이 금융 시스템 전반으로 확산될 가능성은 여전히 경계해야 합니다. 지금이야말로 탄탄한 재정 건전성을 확보하고, 위험을 분산할 수 있는 대안에 투자해야 할 때입니다."""

    print(f"✅ OLD 버전 로드 완료 ({len(old_post)} chars)")

    # Step 5: Evaluate Both Versions
    print("\n" + "=" * 80)
    print("📊 EVALUATION RESULTS")
    print("=" * 80)

    eval_old = evaluate_content_quality(old_post, "Version A (OLD)")
    eval_new = evaluate_content_quality(new_post, "Version B (NEW)")

    print(f"\n{'Version':<20} {'Primary KPI':<15} {'Length':<10} {'Specificity':<15} {'Actionability':<15} {'CTA':<10}")
    print("-" * 95)
    print(
        f"{eval_old['version']:<20} {eval_old['primary_kpi']:<15} {eval_old['breakdown']['length']['value']:<10} {eval_old['breakdown']['specificity']['score']:<15} {eval_old['breakdown']['actionability']['score']:<15} {eval_old['breakdown']['cta_clarity']['score']:<10}"
    )
    print(
        f"{eval_new['version']:<20} {eval_new['primary_kpi']:<15} {eval_new['breakdown']['length']['value']:<10} {eval_new['breakdown']['specificity']['score']:<15} {eval_new['breakdown']['actionability']['score']:<15} {eval_new['breakdown']['cta_clarity']['score']:<10}"
    )

    # Step 6: Decision
    print("\n" + "=" * 80)
    print("✅ DECISION")
    print("=" * 80)

    kpi_diff = eval_new["primary_kpi"] - eval_old["primary_kpi"]
    passes_secondary = sum(
        [
            eval_new["passes_criteria"]["length_optimal"],
            eval_new["passes_criteria"]["min_specificity"],
            eval_new["passes_criteria"]["has_actionability"],
        ]
    )

    target_kpi_gain = 15  # from hypothesis
    print(f"Primary KPI 차이: {kpi_diff:+.1f}점 (Target: +{target_kpi_gain}점)")
    print(f"Secondary 통과: {passes_secondary}/3개 (Target: 2개 이상)")

    if kpi_diff >= target_kpi_gain and passes_secondary >= 2:
        decision = "✅ NEW 버전 채택 권장"
        confidence = "높음"
    elif kpi_diff >= 10:
        decision = "⚠️ NEW 버전 조건부 채택 (추가 샘플 필요)"
        confidence = "중간"
    else:
        decision = "❌ OLD 버전 유지 또는 재설계 필요"
        confidence = "낮음"

    print(f"\n결정: {decision}")
    print(f"신뢰도: {confidence}")

    # Step 7: Recommendations
    print("\n" + "=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)

    recommendations = []

    if eval_new["breakdown"]["specificity"]["count"] < 2:
        recommendations.append("- 구체적 숫자/데이터 포인트를 최소 2개 이상 포함하도록 프롬프트 개선")

    if not eval_new["passes_criteria"]["has_cta"]:
        recommendations.append("- 명확한 CTA 또는 행동 가이드를 마지막 문단에 추가")

    if eval_new["breakdown"]["length"]["value"] > 800:
        recommendations.append("- 모바일 가독성을 위해 콘텐츠 길이를 800자 이하로 제한")

    if eval_new["breakdown"]["actionability"]["score"] < 50:
        recommendations.append("- 독자의 실생활 적용 가능한 인사이트 강화 (예: '이번 주 주목할 지표는...')")

    if recommendations:
        print("개선 권장사항:")
        for rec in recommendations:
            print(rec)
    else:
        print("✅ 현재 버전이 Audience-First 기준을 충족합니다.")

    # Step 8: Next Steps
    print("\n" + "=" * 80)
    print("📌 NEXT STEPS")
    print("=" * 80)
    print("1. 실제 X 배포: 각 버전 20개씩 랜덤 게시 (A/B 스플릿)")
    print("2. 인게이지먼트 측정: 좋아요+RT+답글/조회수 (7일간)")
    print("3. 정성 피드백: 댓글/DM에서 독자 반응 분석")
    print("4. 최종 결정: 통계적 유의성 확인 후 버전 확정")
    print("5. 파이프라인 업데이트: 승리 버전의 프롬프트/구조를 표준으로 설정")

    # Step 9: Save Report
    output_dir = settings.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "ab_test_economy_kr_v2.json"

    report = {
        "test_date": datetime.now().isoformat(),
        "audience_profile": AUDIENCE_PROFILE,
        "hypothesis": AB_TEST_HYPOTHESIS,
        "evaluation": {
            "version_a": eval_old,
            "version_b": eval_new,
        },
        "decision": {
            "kpi_difference": kpi_diff,
            "secondary_passes": passes_secondary,
            "verdict": decision,
            "confidence": confidence,
        },
        "recommendations": recommendations,
        "content_samples": {
            "version_a": old_post,
            "version_b": new_post,
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Full Report saved: {output_path}")

    # Also save markdown version
    md_path = output_dir / "ab_test_economy_kr_v2.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Economy_KR A/B Test v2.0 — Audience-First Validation\n\n")
        f.write(f"**Test Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("---\n\n")
        f.write("## 🎯 Audience Profile\n\n")
        f.write(f"- **Type**: {AUDIENCE_PROFILE['type']}\n")
        f.write(f"- **Target**: {AUDIENCE_PROFILE['target_persona']['primary']}\n")
        f.write(
            f"- **Pain Points**: {', '.join(AUDIENCE_PROFILE['target_persona']['psychographics']['pain_points'])}\n"
        )
        f.write(f"- **Channel**: {AUDIENCE_PROFILE['consumption_context']['channel']}\n\n")
        f.write("---\n\n")
        f.write("## 🧪 Hypothesis\n\n")
        f.write(f"{AB_TEST_HYPOTHESIS['hypothesis']}\n\n")
        f.write(f"**Version A**: {AB_TEST_HYPOTHESIS['version_a']['description']}\n")
        f.write(f"**Version B**: {AB_TEST_HYPOTHESIS['version_b']['description']}\n\n")
        f.write("---\n\n")
        f.write("## 📊 Results\n\n")
        f.write("| Version | Primary KPI | Length | Specificity | Actionability | CTA |\n")
        f.write("|---------|-------------|--------|-------------|---------------|-----|\n")
        f.write(
            f"| Version A (OLD) | {eval_old['primary_kpi']} | {eval_old['breakdown']['length']['value']} | {eval_old['breakdown']['specificity']['score']} | {eval_old['breakdown']['actionability']['score']} | {eval_old['breakdown']['cta_clarity']['score']} |\n"
        )
        f.write(
            f"| Version B (NEW) | {eval_new['primary_kpi']} | {eval_new['breakdown']['length']['value']} | {eval_new['breakdown']['specificity']['score']} | {eval_new['breakdown']['actionability']['score']} | {eval_new['breakdown']['cta_clarity']['score']} |\n\n"
        )
        f.write(f"**KPI Difference**: {kpi_diff:+.1f} points\n\n")
        f.write(f"**Decision**: {decision}\n\n")
        f.write("---\n\n")
        f.write("## 💡 Recommendations\n\n")
        if recommendations:
            for rec in recommendations:
                f.write(f"{rec}\n")
        else:
            f.write("✅ No critical issues. Current version meets criteria.\n")
        f.write("\n---\n\n")
        f.write("## 📝 Content Samples\n\n")
        f.write("### Version A (OLD)\n\n")
        f.write(f"```\n{old_post}\n```\n\n")
        f.write("### Version B (NEW)\n\n")
        f.write(f"```\n{new_post}\n```\n\n")

    print(f"✅ Markdown Report saved: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_ab_test()))
