"""Reasoning Adapter — 3-step inductive reasoning engine (Popper falsificationism).

Step 1: Extract verifiable fact fragments + "why?" questions
Step 2: Cross-link facts → generate hypotheses (compared to existing patterns)
Step 3: Attempt falsification → promote surviving hypotheses to patterns
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Import LLM primitives with graceful fallback
try:
    from shared.llm import TaskTier, get_client as _get_llm_client
except ImportError:
    try:
        import sys
        from pathlib import Path
        _ROOT = Path(__file__).resolve().parents[4]
        if str(_ROOT) not in sys.path:
            sys.path.insert(0, str(_ROOT))
        from shared.llm import TaskTier, get_client as _get_llm_client
    except ImportError:
        TaskTier = None
        _get_llm_client = None


def _robust_json_parse(text: str) -> dict | list | None:
    """Parse JSON from LLM output, tolerant of markdown fences and line breaks."""
    raw = text

    # Step 1: Strip markdown fences
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]
    raw = raw.strip()

    # Step 2: Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Step 3: Fix line breaks inside JSON string values
    # Replace actual newlines that appear inside quoted strings with spaces
    fixed = re.sub(r'(?<=": ")(.*?)(?=")', lambda m: m.group(0).replace("\n", " "), raw, flags=re.DOTALL)
    # Also fix trailing commas
    fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Step 4: Aggressive — collapse all newlines inside the JSON structure
    collapsed = re.sub(r'\n\s*', ' ', raw)
    collapsed = re.sub(r',(\s*[}\]])', r'\1', collapsed)
    try:
        return json.loads(collapsed)
    except json.JSONDecodeError:
        pass

    # Step 5: Last resort — extract individual JSON objects via regex
    try:
        objects = re.findall(r'\{[^{}]*\}', collapsed)
        if objects:
            parsed = [json.loads(obj) for obj in objects]
            return parsed
    except json.JSONDecodeError:
        pass

    logger.warning("Failed to parse reasoning JSON after all attempts: %s...", text[:200])
    return None


def _load_prompts() -> dict[str, Any]:
    """Load reasoning prompts from config/reasoning_prompts.json."""
    try:
        from antigravity_mcp.config import CONFIG_DIR
        path = CONFIG_DIR / "reasoning_prompts.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


class ReasoningAdapter:
    """3-step inductive reasoning engine based on Popper's falsificationism."""

    def __init__(self, *, state_store: Any | None = None) -> None:
        try:
            self._client = _get_llm_client() if _get_llm_client else None
        except Exception:
            self._client = None
        self._state_store = state_store
        self._prompts = _load_prompts()

    def is_available(self) -> bool:
        return self._client is not None

    # ── Step 1: Extract Facts ─────────────────────────────────────────────

    async def step1_extract_facts(
        self, report_id: str, category: str, content_text: str, source_title: str = ""
    ) -> list[dict[str, str]]:
        """Extract verifiable fact fragments with 'Why is this important?' questions.

        Returns list of {"fact_text": "...", "why_question": "..."}.
        """
        if not self.is_available():
            return []

        step1_cfg = self._prompts.get("step1_extract_facts", {})
        system_msg = step1_cfg.get("system", "당신은 뉴스 콘텐츠에서 검증 가능한 사실을 추출하는 분석가입니다.")

        prompt = (
            f"{system_msg}\n\n"
            f"아래 콘텐츠에서 검증 가능한 사실을 파편 단위로 추출하세요.\n"
            f"각 사실에 대해 '왜 이것이 중요한가?' 질문을 함께 생성하세요.\n\n"
            f"[콘텐츠]\n{content_text[:3000]}\n\n"
            f"[출력 형식] JSON 배열만 반환:\n"
            f'[{{"fact_text": "검증 가능한 사실", "why_question": "왜 이것이 중요한가?"}}]\n'
            f"최대 8개의 사실을 추출하세요."
        )

        try:
            resp = await self._client.acreate(
                tier=TaskTier.HEAVY,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = _robust_json_parse(resp.text or "")
            if isinstance(parsed, list):
                # Persist to DB if state_store available
                if self._state_store:
                    from antigravity_mcp.domain.models import FactFragment
                    from antigravity_mcp.state.events import utc_now_iso
                    fragments = []
                    for idx, item in enumerate(parsed):
                        fid = hashlib.sha256(
                            f"{report_id}:{idx}:{item.get('fact_text', '')[:50]}".encode()
                        ).hexdigest()[:16]
                        fragments.append(FactFragment(
                            fact_id=fid,
                            report_id=report_id,
                            fact_text=item.get("fact_text", ""),
                            why_question=item.get("why_question", ""),
                            category=category,
                            source_title=source_title,
                            created_at=utc_now_iso(),
                        ))
                    self._state_store.save_fact_fragments(fragments)
                logger.info("[Step1] Extracted %d facts from report %s", len(parsed), report_id)
                return parsed
        except Exception as exc:
            logger.warning("Step 1 failed: %s", exc)
        return []

    # ── Step 2: Hypothesize ───────────────────────────────────────────────

    async def step2_hypothesize(
        self, facts: list[dict[str, str]], existing_patterns: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """Cross-link facts → generate hypotheses, compared to existing patterns.

        Returns list of {"hypothesis": "...", "based_on": ["F-1", ...], "pattern": "..."}.
        """
        if not self.is_available() or not facts:
            return []

        step2_cfg = self._prompts.get("step2_hypothesize", {})
        system_msg = step2_cfg.get("system", "당신은 사실들 사이의 패턴을 발견하는 연구자입니다.")

        facts_text = "\n".join(
            f"F-{i+1}: {f['fact_text']} / WHY: {f.get('why_question', '')}"
            for i, f in enumerate(facts)
        )

        patterns_text = ""
        if existing_patterns:
            patterns_text = "\n[기존 패턴]\n" + "\n".join(
                f"P-{p.get('pattern_id', '?')}: {p.get('pattern_text', '')} (생존 {p.get('survival_count', 0)}회)"
                for p in existing_patterns[:10]
            )

        prompt = (
            f"{system_msg}\n\n"
            f"아래 사실들 사이의 연결 고리를 찾고 가설을 세우세요.\n"
            f"기존 패턴과 어떻게 연결되는지도 설명하세요.\n\n"
            f"[사실 파편]\n{facts_text}\n"
            f"{patterns_text}\n\n"
            f"[출력 형식] JSON 배열만 반환:\n"
            f'[{{"hypothesis": "가설 텍스트", "based_on": ["F-1", "F-3"], "pattern": "연결된 기존 패턴 또는 새로운 패턴"}}]\n'
            f"최대 5개의 가설을 생성하세요."
        )

        try:
            resp = await self._client.acreate(
                tier=TaskTier.HEAVY,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = _robust_json_parse(resp.text or "")
            if isinstance(parsed, list):
                # Persist hypotheses
                if self._state_store:
                    from antigravity_mcp.domain.models import Hypothesis
                    from antigravity_mcp.state.events import utc_now_iso
                    hyps = []
                    for idx, item in enumerate(parsed):
                        hid = hashlib.sha256(
                            f"hyp:{idx}:{item.get('hypothesis', '')[:50]}".encode()
                        ).hexdigest()[:16]
                        hyps.append(Hypothesis(
                            hypothesis_id=hid,
                            hypothesis_text=item.get("hypothesis", ""),
                            based_on_facts=item.get("based_on", []),
                            related_pattern=item.get("pattern", ""),
                            status="pending",
                            created_at=utc_now_iso(),
                        ))
                    self._state_store.save_hypotheses(hyps)
                logger.info("[Step2] Generated %d hypotheses", len(parsed))
                return parsed
        except Exception as exc:
            logger.warning("Step 2 failed: %s", exc)
        return []

    # ── Step 3: Falsify ───────────────────────────────────────────────────

    async def step3_falsify(
        self, hypotheses: list[dict[str, Any]], category: str = ""
    ) -> list[dict[str, Any]]:
        """Attempt falsification of each hypothesis. Promote survivors to patterns.

        Returns list of {"hypothesis": "...", "status": "survived|falsified",
                         "counter": "...", "new_pattern": "..."}.
        """
        if not self.is_available() or not hypotheses:
            return []

        step3_cfg = self._prompts.get("step3_falsify", {})
        system_msg = step3_cfg.get("system", "당신은 가설의 약점을 찾아 반증하는 비판적 사고가입니다.")

        hyp_text = "\n".join(
            f"H-{i+1}: {h.get('hypothesis', '')} (근거: {', '.join(h.get('based_on', []))})"
            for i, h in enumerate(hypotheses)
        )

        prompt = (
            f"{system_msg}\n\n"
            f"각 가설에 대해:\n"
            f"1. 반증할 수 있는 증거나 논리를 제시하세요\n"
            f"2. 반증을 견뎌낸 가설을 '새 연결축'으로 승격하세요\n"
            f"3. 반증된 가설은 '약한 연결'로 표시하세요\n\n"
            f"[가설]\n{hyp_text}\n\n"
            f"[출력 규칙] 반드시 아래 형식의 JSON 배열만 반환하세요. "
            f"값에 줄바꿈을 넣지 마세요. 각 항목은 50자 이내로 간결하게:\n"
            f'[{{"hypothesis": "요약", "status": "survived", "counter": "반증 내용", "new_pattern": "패턴"}}]\n'
            f"status는 반드시 'survived' 또는 'falsified' 중 하나.\n"
            f"falsified인 경우 new_pattern은 빈 문자열(\"\")로."
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
                # Promote survived hypotheses to patterns
                if self._state_store and survived:
                    for item in survived:
                        pattern_text = item.get("new_pattern", item.get("hypothesis", ""))
                        pid = hashlib.sha256(pattern_text[:100].encode()).hexdigest()[:16]
                        self._state_store.upsert_pattern(
                            pattern_id=pid,
                            pattern_text=pattern_text,
                            category=category,
                            evidence_facts=[],
                            strength="emerging",
                        )
                logger.info(
                    "[Step3] %d/%d hypotheses survived falsification",
                    len(survived), len(parsed),
                )
                return parsed
        except Exception as exc:
            logger.warning("Step 3 failed: %s", exc)
        return []

    # ── Full Reasoning Pipeline ───────────────────────────────────────────

    async def run_full_reasoning(
        self, report_id: str, category: str, content_text: str, source_title: str = ""
    ) -> dict[str, Any]:
        """Run all 3 steps end-to-end and return consolidated result."""
        result: dict[str, Any] = {
            "facts": [],
            "hypotheses": [],
            "falsification": [],
            "new_patterns": [],
            "survived_count": 0,
        }

        # Step 1
        facts = await self.step1_extract_facts(report_id, category, content_text, source_title)
        result["facts"] = facts
        if not facts:
            return result

        # Step 2 — feed in existing patterns for cross-linking
        existing_patterns = []
        if self._state_store:
            existing_patterns = self._state_store.get_active_patterns(category)
        hypotheses = await self.step2_hypothesize(facts, existing_patterns)
        result["hypotheses"] = hypotheses
        if not hypotheses:
            return result

        # Step 3
        falsification = await self.step3_falsify(hypotheses, category)
        result["falsification"] = falsification
        survived = [r for r in falsification if r.get("status") == "survived"]
        result["new_patterns"] = [r.get("new_pattern", "") for r in survived if r.get("new_pattern")]
        result["survived_count"] = len(survived)

        logger.info(
            "Reasoning complete for %s: %d facts → %d hypotheses → %d survived",
            category, len(facts), len(hypotheses), len(survived),
        )
        return result
