"""
GetDayTrends Trend Reasoning — 교차 트렌드 귀납적 추론 엔진.

트렌드 스코어링 결과를 입력받아:
  Step 1: 사실 파편 추출 (어떤 키워드가 왜 떴는가)
  Step 2: 교차 연결 → 가설 (왜 이 키워드들이 동시에 뜨는가)
  Step 3: 반증 시도 → 생존 패턴 축적
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Any

try:
    from shared.llm import TaskTier, get_client
except ImportError:
    TaskTier = None
    get_client = None

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
#  Robust JSON Parser (Korean LLM output tolerant)
# ══════════════════════════════════════════════════════


def _robust_json_parse(text: str) -> dict | list | None:
    raw = text
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    fixed = re.sub(r'(?<=": ")(.*?)(?=")', lambda m: m.group(0).replace("\n", " "), raw, flags=re.DOTALL)
    fixed = re.sub(r",(\s*[}\]])", r"\1", fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    collapsed = re.sub(r"\n\s*", " ", raw)
    collapsed = re.sub(r",(\s*[}\]])", r"\1", collapsed)
    try:
        return json.loads(collapsed)
    except json.JSONDecodeError:
        pass

    try:
        objects = re.findall(r"\{[^{}]*\}", collapsed)
        if objects:
            return [json.loads(obj) for obj in objects]
    except json.JSONDecodeError:
        pass

    log.warning("Failed to parse reasoning JSON after all attempts: %s...", text[:200])
    return None


# ══════════════════════════════════════════════════════
#  DB Operations (aiosqlite compatible)
# ══════════════════════════════════════════════════════

REASONING_DDL = """
CREATE TABLE IF NOT EXISTS trend_facts (
    fact_id TEXT PRIMARY KEY,
    run_id TEXT,
    fact_text TEXT,
    why_question TEXT,
    category TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS trend_hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    hypothesis_text TEXT,
    based_on TEXT,
    related_pattern TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS trend_patterns (
    pattern_id TEXT PRIMARY KEY,
    pattern_text TEXT,
    category TEXT,
    strength TEXT DEFAULT 'emerging',
    survival_count INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);
"""


_tables_initialized = False


async def init_reasoning_tables(conn) -> None:
    """Create reasoning tables if not exist (idempotent, runs once per process)."""
    global _tables_initialized
    if _tables_initialized:
        return
    for stmt in REASONING_DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            await conn.execute(stmt)
    await conn.commit()
    _tables_initialized = True
    log.info("[Reasoning] DB tables initialized")


async def get_active_patterns(conn, category: str = "", limit: int = 10) -> list[dict]:
    if category:
        cursor = await conn.execute(
            "SELECT pattern_id, pattern_text, category, survival_count "
            "FROM trend_patterns WHERE category = ? ORDER BY survival_count DESC LIMIT ?",
            (category, limit),
        )
    else:
        cursor = await conn.execute(
            "SELECT pattern_id, pattern_text, category, survival_count "
            "FROM trend_patterns ORDER BY survival_count DESC LIMIT ?",
            (limit,),
        )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def upsert_pattern(conn, pattern_id: str, pattern_text: str, category: str) -> None:
    now = datetime.now().isoformat()
    await conn.execute(
        """INSERT INTO trend_patterns (pattern_id, pattern_text, category, strength, survival_count, created_at, updated_at)
           VALUES (?, ?, ?, 'emerging', 1, ?, ?)
           ON CONFLICT(pattern_id) DO UPDATE SET
               survival_count = survival_count + 1,
               strength = CASE WHEN survival_count + 1 >= 3 THEN 'strong' ELSE 'emerging' END,
               updated_at = ?""",
        (pattern_id, pattern_text, category, now, now, now),
    )
    await conn.commit()


async def save_facts(conn, facts: list[dict], run_id: str, category: str) -> None:
    now = datetime.now().isoformat()
    for idx, f in enumerate(facts):
        fid = hashlib.sha256(f"{run_id}:{idx}:{f.get('fact_text', '')[:50]}".encode()).hexdigest()[:16]
        await conn.execute(
            "INSERT OR IGNORE INTO trend_facts (fact_id, run_id, fact_text, why_question, category, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (fid, run_id, f.get("fact_text", ""), f.get("why_question", ""), category, now),
        )
    await conn.commit()


async def save_hypotheses(conn, hypotheses: list[dict]) -> None:
    now = datetime.now().isoformat()
    for idx, h in enumerate(hypotheses):
        hid = hashlib.sha256(f"hyp:{idx}:{h.get('hypothesis', '')[:50]}".encode()).hexdigest()[:16]
        await conn.execute(
            "INSERT OR IGNORE INTO trend_hypotheses (hypothesis_id, hypothesis_text, based_on, related_pattern, status, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (
                hid,
                h.get("hypothesis", ""),
                json.dumps(h.get("based_on", []), ensure_ascii=False),
                h.get("pattern", ""),
                now,
            ),
        )
    await conn.commit()


# ══════════════════════════════════════════════════════
#  3-Step Reasoning Engine
# ══════════════════════════════════════════════════════


class TrendReasoningAdapter:
    """Cross-trend inductive reasoning engine for GetDayTrends."""

    def __init__(self) -> None:
        try:
            self._client = get_client()
        except Exception:
            self._client = None

    def is_available(self) -> bool:
        return self._client is not None

    async def step1_extract_facts(self, trend_data: str, run_id: str = "") -> list[dict]:
        if not self.is_available():
            return []

        prompt = (
            "당신은 트렌드 데이터에서 검증 가능한 사실을 추출하는 분석가입니다.\n\n"
            "아래 트렌드 스코어링 결과에서 검증 가능한 사실을 추출하세요.\n"
            "각 사실에 '왜 이것이 중요한가?' 질문을 함께 생성하세요.\n\n"
            f"[트렌드 데이터]\n{trend_data[:3000]}\n\n"
            "[출력 규칙] JSON 배열만. 줄바꿈 금지. 최대 8개:\n"
            '[{"fact_text": "검증 가능한 사실", "why_question": "왜 중요한가?"}]'
        )

        try:
            resp = await self._client.acreate(
                tier=TaskTier.HEAVY,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = _robust_json_parse(resp.text or "")
            if isinstance(parsed, list):
                log.info("[Step1] Extracted %d facts", len(parsed))
                return parsed
        except Exception as exc:
            log.warning("Step 1 failed: %s", exc)
        return []

    async def step2_hypothesize(self, facts: list[dict], existing_patterns: list[dict] | None = None) -> list[dict]:
        if not self.is_available() or not facts:
            return []

        facts_text = "\n".join(
            f"F-{i+1}: {f['fact_text']} / WHY: {f.get('why_question', '')}" for i, f in enumerate(facts)
        )

        patterns_text = ""
        if existing_patterns:
            patterns_text = "\n[기존 패턴]\n" + "\n".join(
                f"P-{p.get('pattern_id', '?')}: {p.get('pattern_text', '')} (생존 {p.get('survival_count', 0)}회)"
                for p in existing_patterns[:10]
            )

        prompt = (
            "당신은 트렌드들 사이의 숨겨진 교차 패턴을 발견하는 연구자입니다.\n\n"
            "아래 사실들 사이의 연결 고리를 찾고 가설을 세우세요.\n"
            "'왜 이 키워드들이 동시에 뜨는가?'에 답하세요.\n\n"
            f"[사실 파편]\n{facts_text}\n{patterns_text}\n\n"
            "[출력 규칙] JSON 배열만. 줄바꿈 금지. 최대 5개:\n"
            '[{"hypothesis": "가설", "based_on": ["F-1", "F-3"], "pattern": "패턴"}]'
        )

        try:
            resp = await self._client.acreate(
                tier=TaskTier.HEAVY,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = _robust_json_parse(resp.text or "")
            if isinstance(parsed, list):
                log.info("[Step2] Generated %d hypotheses", len(parsed))
                return parsed
        except Exception as exc:
            log.warning("Step 2 failed: %s", exc)
        return []

    async def step3_falsify(self, hypotheses: list[dict]) -> list[dict]:
        if not self.is_available() or not hypotheses:
            return []

        hyp_text = "\n".join(
            f"H-{i+1}: {h.get('hypothesis', '')} (근거: {', '.join(h.get('based_on', []))})"
            for i, h in enumerate(hypotheses)
        )

        prompt = (
            "당신은 가설의 약점을 찾아 반증하는 비판적 사고가입니다.\n\n"
            "각 가설에 대해:\n"
            "1. 반증할 수 있는 증거나 논리를 제시하세요\n"
            "2. 반증을 견뎌낸 가설을 '새 연결축'으로 승격하세요\n\n"
            f"[가설]\n{hyp_text}\n\n"
            "[출력 규칙] JSON 배열만. 줄바꿈 금지. 각 항목 50자 이내:\n"
            '[{"hypothesis": "요약", "status": "survived", "counter": "반증", "new_pattern": "패턴"}]\n'
            "status: 'survived' 또는 'falsified'. falsified면 new_pattern은 빈 문자열."
        )

        try:
            resp = await self._client.acreate(
                tier=TaskTier.HEAVY,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = _robust_json_parse(resp.text or "")
            if isinstance(parsed, list):
                survived = [r for r in parsed if r.get("status") == "survived"]
                log.info("[Step3] %d/%d survived falsification", len(survived), len(parsed))
                return parsed
        except Exception as exc:
            log.warning("Step 3 failed: %s", exc)
        return []

    async def run_full_reasoning(
        self,
        conn,
        run_id: str,
        category: str,
        trend_data: str,
    ) -> dict[str, Any]:
        """Full 3-step reasoning pipeline."""
        result: dict[str, Any] = {
            "facts": [],
            "hypotheses": [],
            "falsification": [],
            "new_patterns": [],
            "survived_count": 0,
        }

        # Ensure tables
        await init_reasoning_tables(conn)

        # Step 1
        facts = await self.step1_extract_facts(trend_data, run_id)
        result["facts"] = facts
        if not facts:
            return result
        await save_facts(conn, facts, run_id, category)

        # Step 2
        existing_patterns = await get_active_patterns(conn, category)
        hypotheses = await self.step2_hypothesize(facts, existing_patterns)
        result["hypotheses"] = hypotheses
        if not hypotheses:
            return result
        await save_hypotheses(conn, hypotheses)

        # Step 3
        falsification = await self.step3_falsify(hypotheses)
        result["falsification"] = falsification
        survived = [r for r in falsification if r.get("status") == "survived"]
        result["new_patterns"] = [r.get("new_pattern", "") for r in survived if r.get("new_pattern")]
        result["survived_count"] = len(survived)

        # Promote survived to patterns
        for item in survived:
            pattern_text = item.get("new_pattern", item.get("hypothesis", ""))
            pid = hashlib.sha256(pattern_text[:100].encode()).hexdigest()[:16]
            await upsert_pattern(conn, pid, pattern_text, category)

        log.info(
            "Trend reasoning complete: %d facts → %d hyp → %d survived",
            len(facts),
            len(hypotheses),
            len(survived),
        )
        return result
