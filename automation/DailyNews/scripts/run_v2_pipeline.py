"""Full 6-category pipeline with QC scoring and Notion management.

Runs: Deep Collect -> Editorial Filter -> Deep Analysis -> QC Score -> Save to Notion
"""
import asyncio
import json
import logging
import sys
import io
from datetime import date, datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, r"D:\AI project\DailyNews\src")
sys.path.insert(0, r"D:\AI project\DailyNews\scripts")
sys.path.insert(0, r"D:\AI project\packages")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from antigravity_mcp.pipelines.collect import collect_content_items
from antigravity_mcp.integrations.brain_adapter import BrainAdapter
from antigravity_mcp.integrations.reasoning_adapter import ReasoningAdapter
from antigravity_mcp.integrations.digest_adapter import DigestAdapter
from antigravity_mcp.state.store import PipelineStateStore
from antigravity_mcp.config import get_settings

CATEGORIES = ["Tech", "AI_Deep", "Economy_KR", "Economy_Global", "Crypto", "Global_Affairs"]

CATEGORY_LABELS = {
    "Tech": "🔧 Tech",
    "AI_Deep": "🤖 AI Deep Dive",
    "Economy_KR": "🇰🇷 한국 경제",
    "Economy_Global": "🌍 글로벌 경제",
    "Crypto": "₿ Crypto",
    "Global_Affairs": "🌐 국제 정세",
}


async def qc_score(brain: BrainAdapter, category: str, post_text: str) -> dict:
    """Stage 4: Quality Gate — score the post on 3 criteria."""
    from shared.llm import TaskTier
    prompt = (
        "아래 X 롱폼 포스트를 평가하세요.\n\n"
        f"[카테고리]: {category}\n"
        f"[포스트]\n{post_text}\n\n"
        "[평가 기준 — 각각 1~5점]\n"
        "1. **발견**: 독자가 '몰랐던 사실 하나'를 얻는가?\n"
        "2. **통찰**: 뉴스 간 연결, 인과 추론이 있는가?\n"
        "3. **공유성**: 공유했을 때 공유자의 지적 이미지가 올라가는가?\n\n"
        "[추가 체크]\n"
        "- 구체 수치 2개 이상 포함?\n"
        "- 인과 추론 2단계 이상?\n"
        "- '~할 수 있습니다' 같은 모호한 표현 없음?\n"
        "- 시의성: 오늘 이슈와 관련 있는 내용인가?\n\n"
        "반드시 아래 JSON만 반환:\n"
        '{"discovery": N, "insight": N, "shareability": N, '
        '"has_numbers": true/false, "has_causal_chain": true/false, '
        '"has_vague_expr": true/false, "is_timely": true/false, '
        '"feedback": "개선 피드백 1줄"}'
    )
    try:
        resp = await brain._client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (resp.text or "").strip()
        if "{" in text:
            text = text[text.index("{"):text.rindex("}") + 1]
            return json.loads(text)
    except Exception as e:
        logger.warning("QC scoring failed for %s: %s", category, e)
    return {"discovery": 0, "insight": 0, "shareability": 0, "feedback": "QC 실패"}


async def generate_unified_brief(results: dict) -> str:
    """Generate unified morning brief in X Longform format combining all 6 categories."""
    today_str = date.today().isoformat()

    # Header
    brief = f"""# [X Longform] Daily Brief - {today_str}
> 📰 Antigravity Daily Brief - {today_str} 07:00 발행분
6개 카테고리 X 롱폼 포스트 | 자동 생성

---

"""

    # Add each category section
    for cat in CATEGORIES:
        if cat not in results:
            continue

        r = results[cat]
        label = CATEGORY_LABELS.get(cat, cat)
        post = r.get("post", "")

        brief += f"""## {label}

{post}

---

"""

    return brief


async def publish_to_notion(results: dict):
    """Publish QC'd results as a structured Notion page."""
    from settings import NOTION_API_KEY, ANTIGRAVITY_TASKS_DB_ID
    from notion_client import AsyncClient

    notion = AsyncClient(auth=NOTION_API_KEY)
    db_id = ANTIGRAVITY_TASKS_DB_ID
    if len(db_id) == 32 and "-" not in db_id:
        db_id = f"{db_id[:8]}-{db_id[8:12]}-{db_id[12:16]}-{db_id[16:20]}-{db_id[20:]}"

    today_str = date.today().isoformat()
    children = []

    # Generate unified brief first
    unified_brief = await generate_unified_brief(results)

    # Header - Unified Morning Brief
    children.append({
        "object": "block", "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": "📰"},
            "rich_text": [{"type": "text", "text": {"content":
                f"Antigravity Daily Brief - {today_str} 07:00 발행분\n"
                f"6개 카테고리 X 롱폼 포스트 | 자동 생성"
            }}],
            "color": "blue_background",
        }
    })

    # Add unified brief as code block for easy copy
    children.append({
        "object": "block", "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": "📋 통합 모닝 브리핑 (X Thread Format)"}}]}
    })

    # Split unified brief into chunks (Notion has 2000 char limit per block)
    brief_lines = unified_brief.split('\n')
    current_chunk = []
    current_len = 0

    for line in brief_lines:
        line_len = len(line) + 1  # +1 for newline
        if current_len + line_len > 1900:  # Leave margin
            # Flush current chunk
            chunk_text = '\n'.join(current_chunk)
            children.append({
                "object": "block", "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": chunk_text}}],
                    "language": "markdown"
                }
            })
            current_chunk = [line]
            current_len = line_len
        else:
            current_chunk.append(line)
            current_len += line_len

    # Flush remaining
    if current_chunk:
        chunk_text = '\n'.join(current_chunk)
        children.append({
            "object": "block", "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": chunk_text}}],
                "language": "markdown"
            }
        })

    children.append({"object": "block", "type": "divider", "divider": {}})

    # QC Details Header
    children.append({
        "object": "block", "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": "📊"},
            "rich_text": [{"type": "text", "text": {"content":
                f"QC Details - 개별 카테고리 분석\n"
                f"3-Stage Pipeline: Deep Collect → Editorial Filter → Deep Analysis → QC"
            }}],
            "color": "gray_background",
        }
    })
    children.append({"object": "block", "type": "divider", "divider": {}})

    total_score = 0
    count = 0

    for cat in CATEGORIES:
        if cat not in results:
            continue

        r = results[cat]
        label = CATEGORY_LABELS.get(cat, cat)
        qc = r.get("qc", {})
        avg = round((qc.get("discovery", 0) + qc.get("insight", 0) + qc.get("shareability", 0)) / 3, 1)
        total_score += avg
        count += 1

        # Category heading with QC score
        children.append({
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {
                "content": f"{label} — QC: {avg}/5"
            }}]},
        })

        # QC details callout
        qc_text = (
            f"발견: {qc.get('discovery', '?')}/5 | "
            f"통찰: {qc.get('insight', '?')}/5 | "
            f"공유성: {qc.get('shareability', '?')}/5\n"
            f"수치: {'✅' if qc.get('has_numbers') else '❌'} | "
            f"인과추론: {'✅' if qc.get('has_causal_chain') else '❌'} | "
            f"시의성: {'✅' if qc.get('is_timely') else '❌'} | "
            f"모호표현: {'없음 ✅' if not qc.get('has_vague_expr') else '있음 ❌'}\n"
            f"피드백: {qc.get('feedback', '')}"
        )
        children.append({
            "object": "block", "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "📋"},
                "rich_text": [{"type": "text", "text": {"content": qc_text}}],
                "color": "gray_background",
            }
        })

        # Post content
        post = r.get("post", "")
        paragraphs = post.replace("\\n", "\n").split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(para) > 1990:
                para = para[:1990] + "..."
            children.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": para}}]},
            })

        children.append({"object": "block", "type": "divider", "divider": {}})

    # Overall score
    overall = round(total_score / max(count, 1), 1)

    page = await notion.pages.create(
        parent={"database_id": db_id},
        properties={
            "Name": {"title": [{"text": {"content": f"Morning Brief - {today_str} (QC: {overall}/5)"}}]},
            "Type": {"select": {"name": "News"}},
            "Date": {"date": {"start": today_str}},
        },
        children=children,
    )
    return page.get("url", ""), overall


async def run_full_pipeline():
    settings = get_settings()
    state_store = PipelineStateStore(settings.pipeline_state_db)
    brain = BrainAdapter()
    reasoner = ReasoningAdapter(state_store=state_store)
    digester = DigestAdapter(state_store=state_store)

    if not brain.is_available():
        print("[ERROR] BrainAdapter not available")
        return

    print(f"{'=' * 60}")
    print(f"DailyNews v2 Full Pipeline - {date.today().isoformat()}")
    print(f"{'=' * 60}\n")

    all_results = {}

    for cat in CATEGORIES:
        print(f"\n{'-' * 40}")
        print(f"[{cat}] Starting pipeline...")
        print(f"{'-' * 40}")

        # Stage 1: Deep Collect
        items, warnings = await collect_content_items(
            categories=[cat],
            window_name="evening",
            max_items=10,
            state_store=state_store,
            fetch_bodies=True,
        )

        if not items:
            # Fallback to 24h window
            items, warnings = await collect_content_items(
                categories=[cat],
                window_name="24h",
                max_items=10,
                state_store=state_store,
                fetch_bodies=True,
            )

        body_count = sum(1 for i in items if i.full_text)
        print(f"  Collected: {len(items)} articles ({body_count} with body text)")

        if not items:
            print(f"  ⚠️ No articles for {cat}, skipping")
            continue

        # Prepare for brain adapter
        articles = [{
            "title": i.title,
            "description": i.summary,
            "summary": i.summary,
            "full_text": i.full_text,
            "source_name": i.source_name,
            "link": i.link,
        } for i in items]

        # Stage 2+3: Editorial Filter + Deep Analysis
        result = await brain.analyze_news(
            category=cat,
            articles=articles,
            time_window=f"{date.today().isoformat()} evening",
        )

        if not result:
            print(f"  ❌ Analysis failed for {cat}")
            continue

        x_thread = result.get("x_thread", [])
        post_text = x_thread[0] if x_thread else ""

        if not post_text:
            print(f"  ❌ No post generated for {cat}")
            continue

        print(f"  ✅ Post: {len(post_text)} chars")

        # Stage 4: QC Score
        qc = await qc_score(brain, cat, post_text.replace("\\n", "\n"))
        avg = round((qc.get("discovery", 0) + qc.get("insight", 0) + qc.get("shareability", 0)) / 3, 1)
        timely = "✅" if qc.get("is_timely") else "❌"
        print(f"  QC: {avg}/5 | 시의성: {timely} | {qc.get('feedback', '')}")

        # Stage 5: Inductive Reasoning
        reasoning_patterns = []
        if reasoner.is_available():
            try:
                content_for_reasoning = "\n".join(
                    f"{a['title']}: {a.get('summary', '')[:200]}" for a in articles
                )
                reasoning_result = await reasoner.run_full_reasoning(
                    report_id=f"v2-{cat}-{date.today().isoformat()}",
                    category=cat,
                    content_text=content_for_reasoning,
                    source_title=f"{cat} v2 pipeline",
                )
                survived = reasoning_result.get("survived_count", 0)
                reasoning_patterns = reasoning_result.get("new_patterns", [])
                facts_count = len(reasoning_result.get("facts", []))
                hyp_count = len(reasoning_result.get("hypotheses", []))
                print(f"  🧠 Reasoning: {facts_count} facts → {hyp_count} hyp → {survived} survived")
                if reasoning_patterns:
                    for p in reasoning_patterns[:2]:
                        print(f"     → {p[:60]}...")
            except Exception as exc:
                logger.warning("Reasoning failed for %s: %s", cat, exc)

        # Enqueue for Digest
        digester.enqueue(f"v2-{cat}-{date.today().isoformat()}")

        all_results[cat] = {
            "post": post_text,
            "summary": result.get("summary", []),
            "insights": result.get("insights", []),
            "reasoning_patterns": reasoning_patterns,
            "qc": qc,
            "article_count": len(items),
            "body_count": body_count,
        }

    # Stage 6: Cross-Category Digest
    if all_results and digester.is_available():
        print(f"\n{'─' * 40}")
        print("Generating cross-category Digest...")
        digest_data = [
            {
                "report_id": f"v2-{cat}-{date.today().isoformat()}",
                "category": cat,
                "summary_lines": r.get("summary", []),
                "insights": r.get("insights", []),
            }
            for cat, r in all_results.items()
        ]
        digest_result = await digester.generate_digest(digest_data)
        if digest_result.get("summary"):
            print(f"  📋 Digest: {digest_result['summary'][:80]}...")
            print(f"  Themes: {digest_result.get('key_themes', '')}")
            print(f"  Outlook: {digest_result.get('outlook', '')}")
        else:
            print("  ⚠️ Digest generation skipped")

    # Publish to Notion
    if all_results:
        print(f"\n{'=' * 60}")
        print("Publishing QC'd results to Notion...")
        url, overall = await publish_to_notion(all_results)
        print(f"  ✅ Published: {url}")
        print(f"  Overall QC Score: {overall}/5")
        print(f"  Categories: {len(all_results)}/{len(CATEGORIES)}")

    # Save local backup
    output_path = Path(r"D:\AI project\automation\DailyNews\output")
    output_path.mkdir(parents=True, exist_ok=True)
    backup = output_path / f"v2_pipeline_{date.today().isoformat()}.json"
    with open(backup, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"  Local backup: {backup}")


if __name__ == "__main__":
    asyncio.run(run_full_pipeline())
