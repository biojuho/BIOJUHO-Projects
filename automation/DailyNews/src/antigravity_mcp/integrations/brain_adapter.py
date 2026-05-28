"""Brain module adapter — cross-article LLM analysis with trend integration.

Consolidated from legacy ``scripts/brain_module.py`` to eliminate duplication.
Includes per-category prompt hints and structured X thread generation.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


def _deep_insight_mode_enabled() -> bool:
    """Single-topic deep insight mode flag (default ON, opt-out via env)."""
    raw = os.getenv("DAILYNEWS_DEEP_INSIGHT_MODE", "1").strip().lower()
    return raw not in ("0", "false", "off", "no")


def _deep_insight_retry_enabled() -> bool:
    """One-shot QC retry on warnings (default OFF, opt-in via env).

    When enabled, a single repair pass is attempted whenever
    ``validate_deep_insight`` returns ``ok == False`` on the first
    LLM response. The retry only replaces the result when it has
    *strictly fewer* warnings. Doubles cost when triggered, so the
    flag is OFF by default; operators turn it on once the baseline
    pass-rate justifies the spend.
    """
    raw = os.getenv("DAILYNEWS_DEEP_INSIGHT_RETRY", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _deep_insight_repair_prompt(prior_warnings: list[str]) -> str:
    """Repair-pass directive appended to the original prompt on retry."""
    if not prior_warnings:
        return ""
    return (
        "\n[재시도 — 직전 출력의 누락 항목을 보강해 다시 작성]\n"
        f"- 직전 시도에서 누락·미달한 항목: {', '.join(prior_warnings)}\n"
        "- 5섹션 구조와 단일 thesis는 그대로 유지하되 위 항목을 반드시 충족시킬 것.\n"
        "- 새 증거 태그·수치 앵커를 추가할 때도 사실 변형은 금지(원본 기사 사실관계 준수).\n"
    )


_DEEP_INSIGHT_DIRECTIVES = (
    "\n[단일 주제 수렴 모드 — 이 모드가 위 작성 규칙보다 우선한다]\n"
    "- 선택된 기사들을 '하나의 주제(Single Thesis)'로 수렴해 분석한다. 기사마다 분리된 섹션을 만들지 말 것.\n"
    "- 오늘의 단 하나의 핵심 신호(Signal)를 식별하고, 그것을 중심으로 큰 흐름·파급·반론·행동을 일관된 한 편의 글로 묶는다.\n"
    "- 본문은 아래 5개 섹션 흐름을 정확히 따른다 (헤더의 영문 키워드는 그대로 유지, 본문은 한국어):\n"
    "  ## 🎯 Signal — 오늘의 단일 핵심 신호 (구체 수치 + 시점)\n"
    "  ## 🔁 Pattern — 이 신호가 속한 더 큰 흐름 (전년/전월/전분기 대비 비교 수치)\n"
    "  ## 🌊 Ripple — 1차·2차 파급, 영향받는 이해관계자 이름까지 명시\n"
    "  ## ⚠️ Counterpoint — 시그널을 반박하는 데이터·시나리오 (필수 — '없음' 금지)\n"
    "  ## ✅ Action — 독자 유형별 행동 1~2개 (시점·대상·구체 행동 모두 명시)\n"
    "- 모든 분석 문장 끝에 증거 태그 하나를 붙인다: [A1], [A2], [Inference:A1+A2], [Background], [Insufficient evidence] 중 하나.\n"
    "- 수치 앵커는 본문 전체에서 최소 3개, Counterpoint 최소 1개, Action의 시점(이번 주/이번 달/이번 분기/연말 등) 명시는 필수.\n"
    "- x_thread는 위 5개 헤더가 모두 들어간 '단일 한 편의 글' 하나로 작성한다 (배열 길이 1).\n"
    "- summary 3줄은 Signal/Pattern/Ripple 세 축을 각각 한 줄로 압축한 형태로 작성한다 (서로 다른 사건이 아니라 같은 thesis의 세 측면).\n"
    "- 각 섹션 첫 문장 패턴(주제·수치만 바꿔서 동일 밀도 재현): '오늘 X는 **5.2%** 변동했다 [A1].' — 굵게 강조된 수치 1개 + 증거 태그 1개를 반드시 포함.\n"
)


_EVIDENCE_TAG_RE = re.compile(r"\[A\d+\]|\[Inference:[^\]]+\]|\[Background\]|\[Insufficient evidence\]")
_NUMBER_ANCHOR_RE = re.compile(
    r"\d[\d,.]*\s*(?:%|원|달러|\$|€|¥|억|만|조|배|건|명|bp|p|개|년|개월|주|일|시간|분)"
)
_COUNTERPOINT_RE = re.compile(r"그러나|하지만|반론|반대로|역으로|다만|단,|역설적|반박|However")
_ACTION_TIMEFRAME_RE = re.compile(
    r"오늘|내일|이번 주|이번 달|이번 분기|이번 주말|3개월|6개월|연말|상반기|하반기|1년 내|단기|중기|장기"
)


def validate_deep_insight(analysis: Any) -> dict[str, Any]:
    """Lightweight quality gate for single-topic deep mode output.

    Returns a dict with ``ok`` (bool), ``warnings`` (list[str]), and
    ``metrics`` (dict). Never raises so it is safe to call from a
    pipeline path that must not be blocked by validation logic.
    """
    if not isinstance(analysis, dict):
        return {"ok": False, "warnings": ["analysis is not a dict"], "metrics": {}}

    x_thread = analysis.get("x_thread") or []
    if isinstance(x_thread, str):
        x_thread = [x_thread]
    x_text = "\n".join(str(s) for s in x_thread)

    tag_count = len(_EVIDENCE_TAG_RE.findall(x_text))
    num_count = len(_NUMBER_ANCHOR_RE.findall(x_text))
    has_counter = bool(_COUNTERPOINT_RE.search(x_text))
    has_action = bool(_ACTION_TIMEFRAME_RE.search(x_text))

    warnings: list[str] = []
    if tag_count < 3:
        warnings.append(f"evidence_tags={tag_count} (min 3 expected)")
    if num_count < 3:
        warnings.append(f"number_anchors={num_count} (min 3 expected)")
    if not has_counter:
        warnings.append("counterpoint_marker missing")
    if not has_action:
        warnings.append("action_timeframe missing")

    return {
        "ok": not warnings,
        "warnings": warnings,
        "metrics": {
            "evidence_tags": tag_count,
            "number_anchors": num_count,
            "has_counterpoint": has_counter,
            "has_action_timeframe": has_action,
            "x_thread_length": len(x_text),
        },
    }

# Import LLM primitives with graceful fallback
try:
    from shared.llm import TaskTier
    from shared.llm import get_client as _get_llm_client
except ImportError:
    try:
        import sys
        from pathlib import Path

        _ROOT = Path(__file__).resolve().parents[4]
        if str(_ROOT) not in sys.path:
            sys.path.insert(0, str(_ROOT))
        from shared.llm import TaskTier
        from shared.llm import get_client as _get_llm_client
    except ImportError:
        TaskTier = None
        _get_llm_client = None

# Per-category prompt hints (migrated from scripts/brain_module.py)
_CATEGORY_PROMPT_HINTS: dict[str, dict[str, str]] = {
    "Tech": {
        "role": "기술/AI/소프트웨어 뉴스를 전문적으로 다루는",
        "focus": "기술 트렌드, AI 혁신, 개발자 생태계, 빅테크 동향에 집중하세요.",
        "tone": "캐주얼하고 신뢰감 있는 전문가 톤",
    },
    "Economy_KR": {
        "role": "한국 경제/금융 뉴스를 전문적으로 분석하는",
        "focus": "국내 증시, 금리, 환율, 부동산, 수출입 동향, 기업 실적에 집중하세요.",
        "tone": "전문적이면서도 대중이 이해하기 쉬운 해설 톤",
    },
    "Economy_Global": {
        "role": "글로벌 경제/금융 시장을 전문적으로 분석하는",
        "focus": "미국 연준, 글로벌 증시, 원자재, 무역 정책, 거시경제 지표에 집중하세요.",
        "tone": "글로벌 시각으로 분석하는 전문가 톤",
    },
    "Crypto": {
        "role": "암호화폐/블록체인 시장을 전문적으로 다루는",
        "focus": "비트코인/이더리움 가격, DeFi, 규제 동향, 온체인 데이터, 거래소 뉴스에 집중하세요.",
        "tone": "크립토 커뮤니티에 맞는 캐주얼하면서도 날카로운 분석 톤",
    },
    "Global_Affairs": {
        "role": "국제 정치/외교 뉴스를 전문적으로 분석하는",
        "focus": "지정학적 갈등, 외교 협상, 선거/정권 변동, 국제기구 동향, 인도적 이슈에 집중하세요.",
        "tone": "객관적이면서도 통찰력 있는 국제뉴스 해설 톤",
    },
    "AI_Deep": {
        "role": "AI/ML 최신 기술과 연구 동향을 깊이 있게 분석하는",
        "focus": "신규 모델 릴리스, 벤치마크 결과, 오픈소스 생태계, AI 안전성/정렬, 에이전트 아키텍처, 멀티모달, 추론 능력, 산업 적용 사례에 집중하세요.",
        "tone": "기술적 깊이를 유지하면서도 실무 개발자가 바로 활용할 수 있는 인사이트를 제공하는 전문가 톤",
    },
}


def _robust_json_parse(text: str) -> dict | None:
    """Parse JSON from LLM output, tolerant of markdown fences and trailing commas."""
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        text = text.strip()
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        text = re.sub(r",(\s*[}\]])", r"\1", text)
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse brain module JSON: %s...", text[:100])
        return None


def _selected_news_text(articles: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for idx, art in enumerate(articles, 1):
        full = art.get("full_text") or ""
        summary = (art.get("description") or art.get("summary") or "")[:200]
        content = full if full else summary
        lines.append(f"[기사 {idx}] {art['title']}\n출처: {art.get('source_name', '알 수 없음')}\n{content}\n")
    return "\n".join(lines)


def _niche_trends_text(niche_trends: list[dict] | None) -> str:
    if not niche_trends:
        return ""
    lines = ["[X Radar 실시간 반응 분석]"]
    for trend in niche_trends[:3]:
        lines.extend(
            [
                f"- 키워드: {trend.get('keyword')}",
                f"  - 반응 인사이트: {trend.get('top_insight')}",
                f"  - 바이럴 포텐셜 점수: {trend.get('viral_potential')}/100",
                f"  - 추천 앵글: {', '.join(trend.get('suggested_angles', []))}",
            ]
        )
    return "\n".join(lines) + "\n"


def _load_x_prompt_rules() -> str:
    try:
        from antigravity_mcp.config import CONFIG_DIR

        prompt_file = CONFIG_DIR / "x_longform_prompt.json"
        if prompt_file.exists():
            prompt_config = json.loads(prompt_file.read_text(encoding="utf-8"))
            return prompt_config.get("x_longform", {}).get("template", "")
    except Exception:
        return ""
    return ""


def _editorial_listing(articles: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for idx, art in enumerate(articles):
        title = art.get("title", "")
        summary = (art.get("summary") or art.get("description") or "")[:200]
        lines.append(f"{idx}. {title}\n   {summary}\n")
    return "\n".join(lines)


def _valid_selected_indices(text: str, article_count: int) -> list[int]:
    if "[" not in text or "]" not in text:
        return []
    arr_text = text[text.index("[") : text.index("]") + 1]
    indices = json.loads(arr_text)
    return [idx for idx in indices if isinstance(idx, int) and 0 <= idx < article_count]


class BrainAdapter:
    """Cross-article analysis: editorial selection + deep insight generation."""

    def __init__(self) -> None:
        try:
            self._client = _get_llm_client() if _get_llm_client else None
        except Exception:
            self._client = None

    def is_available(self) -> bool:
        return self._client is not None

    async def select_top_articles(
        self,
        category: str,
        articles: list[dict[str, str]],
    ) -> list[int]:
        """Stage 2: Pick 3-4 highest-value articles for deep analysis.

        Returns indices of selected articles.
        """
        if not self.is_available() or len(articles) <= 4:
            return list(range(len(articles)))

        hints = _CATEGORY_PROMPT_HINTS.get(category, _CATEGORY_PROMPT_HINTS["Tech"])

        prompt = (
            f"당신은 {hints['role']} 시니어 편집자입니다.\n"
            f"오늘 날짜는 {__import__('datetime').date.today().isoformat()}입니다.\n\n"
            "아래 기사 목록에서 **발행 가치가 가장 높은 3~4개**만 선택하세요.\n\n"
            "[선별 기준]\n"
            "1. **시의성**: 오늘 또는 어제 발생한 사건인가? 과거 뉴스의 재탕이면 제외.\n"
            "2. 시장/사회 영향도: 독자의 의사결정에 영향을 주는가?\n"
            "3. 수치 포함: 구체적 데이터가 있어 분석이 가능한가?\n"
            "4. 연결 가능성: 다른 뉴스와 엮어 더 큰 그림을 그릴 수 있는가?\n"
            "5. 참신성: 독자가 이미 아는 내용의 반복이 아닌가?\n\n"
            "[버리는 기사]\n"
            "- 며칠 전 사건의 후속 보도이면서 새로운 정보가 없는 기사\n"
            "- 단순 이벤트 고지, 기업 PR, 중복 기사\n"
            "- 카테고리와 맞지 않는 기사 (예: 경제 카테고리에 북한 외교 기사)\n\n"
            f"[기사 목록]\n{_editorial_listing(articles)}\n"
            "선택한 기사의 번호만 JSON 배열로 반환하세요. 예: [0, 2, 5]\n"
            "번호 외에 아무 텍스트도 출력하지 마세요."
        )

        try:
            resp = await self._client.acreate(
                tier=TaskTier.LIGHTWEIGHT,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            text = (resp.text or "").strip()
            valid = _valid_selected_indices(text, len(articles))
            if valid:
                logger.info("[%s] Editorial filter: selected %d/%d articles", category, len(valid), len(articles))
                return valid
        except Exception as exc:
            logger.warning("Editorial filter failed for %s: %s", category, exc)

        return list(range(min(4, len(articles))))

    async def analyze_news(
        self,
        category: str,
        articles: list[dict[str, str]],
        time_window: str = "",
        niche_trends: list[dict] | None = None,
    ) -> dict[str, Any] | None:
        """Generate deep analysis with editorial selection.

        Returns None on failure so pipelines can gracefully degrade.
        """
        if not self.is_available() or not articles:
            return None

        # Stage 2: Editorial selection
        selected_indices = await self.select_top_articles(category, articles)
        selected_articles = [articles[i] for i in selected_indices]

        news_text = _selected_news_text(selected_articles)
        trends_text = _niche_trends_text(niche_trends)
        hints = _CATEGORY_PROMPT_HINTS.get(category, _CATEGORY_PROMPT_HINTS["Tech"])

        x_prompt_rules = _load_x_prompt_rules()

        # Stage 3: Deep analysis prompt — newsletter multi-section format
        prompt = (
            f"당신은 {hints['role']} 한국어 뉴스레터 편집자입니다.\n"
            f"[톤]: {hints['tone']}\n"
            f"[집중 포인트]: {hints['focus']}\n"
            f"[분석 기간]: {time_window}\n\n"
            f"[기사 원문]\n{news_text}\n"
            f"{trends_text}\n"
            "============================\n"
            "[독자]\n"
            "30~50대 한국 직장인·자영업자. 헤드라인은 봤지만 맥락을 모른다.\n"
            "자기 삶·자산에 영향을 주는 변화를 미리 감지하고 싶다. 당장 행동할 사람이 아니라 잠재적 당사자.\n\n"
            "[작성 규칙]\n"
            "- 기사마다 별도 섹션으로 분리. 각 섹션은 독립적으로 읽힐 수 있어야 한다.\n"
            "- 섹션 제목: ## {이모지} {핵심 수치 또는 키워드가 들어간 제목} (예: ## 📉 비트코인 $69,355 — 옵션 시장이 보내는 경고)\n"
            "- 첫 문장: 무슨 일인지 즉시 전달 (요약 아닌 훅)\n"
            "- **볼드**로 핵심 수치·용어 강조\n"
            "- 비유/아날로지 금지: 크기감은 기준 수치, 전년 대비, 이해관계자 영향으로 설명\n"
            "- 인과 추론 2단계 이상: '이렇게 되면 → 저렇게 되고 → 결국 이게 바뀐다'\n"
            "- 마지막 문장: 독자가 기억할 한 줄 관점 (긴급 지시 아님)\n"
            "- 각 섹션 길이: 3~4 문단\n\n"
            "[금지]\n"
            "- '시사합니다', '중요합니다', '필요합니다' 결론 없는 마무리\n"
            "- '~할 수 있습니다', '~로 보입니다' 모호한 문장\n"
            "- 비유, 은유, '마치', '~같다', '~처럼'으로 핵심을 설명하는 문장\n"
            "- 수치 없는 주장\n"
            "- 해시태그(#)\n"
            "- '지금 당장 ~하세요' 긴급 지시\n\n"
            "[출력 형식]\n"
            "반드시 아래 JSON만 반환. JSON 내 줄바꿈은 \\n으로.\n"
            '{"tagline": "오늘을 관통하는 핵심 한 줄 (예: 겉은 잔잔하고, 속은 갈라지고 있다)", '
            '"summary": ["핵심 발견 1", "핵심 발견 2", "핵심 발견 3"], '
            '"insights": [{"date": "YYYY-MM-DD", "topic": "주제", "insight": "핵심 분석 (수치 포함)", "importance": "독자에게 의미하는 바"}], '
            '"x_thread": ["## {이모지} {제목1}\\n\\n[섹션1 본문]\\n\\n## {이모지} {제목2}\\n\\n[섹션2 본문]\\n\\n..."]}'
        )
        deep_mode = _deep_insight_mode_enabled()
        if deep_mode:
            prompt += _DEEP_INSIGHT_DIRECTIVES
        if x_prompt_rules:
            prompt += f"\n\n[추가 롱폼 규칙]\n{x_prompt_rules}"

        try:
            resp = await self._client.acreate(
                tier=TaskTier.HEAVY,
                max_tokens=4500 if deep_mode else 3000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = (resp.text or "").strip()
            if not text:
                return None
            result = _robust_json_parse(text)
            if result and deep_mode:
                qc = validate_deep_insight(result)
                if qc["warnings"]:
                    logger.info(
                        "[%s] deep-insight QC warnings: %s | metrics=%s",
                        category,
                        qc["warnings"],
                        qc["metrics"],
                    )
                    if not qc["ok"] and _deep_insight_retry_enabled():
                        repair_prompt = prompt + _deep_insight_repair_prompt(qc["warnings"])
                        try:
                            resp2 = await self._client.acreate(
                                tier=TaskTier.HEAVY,
                                max_tokens=4500,
                                messages=[{"role": "user", "content": repair_prompt}],
                            )
                            text2 = (resp2.text or "").strip()
                            result2 = _robust_json_parse(text2) if text2 else None
                            if result2:
                                qc2 = validate_deep_insight(result2)
                                if len(qc2["warnings"]) < len(qc["warnings"]):
                                    logger.info(
                                        "[%s] deep-insight retry improved: %d → %d warnings",
                                        category,
                                        len(qc["warnings"]),
                                        len(qc2["warnings"]),
                                    )
                                    result = result2
                                else:
                                    logger.info(
                                        "[%s] deep-insight retry kept original (warnings %d → %d)",
                                        category,
                                        len(qc["warnings"]),
                                        len(qc2["warnings"]),
                                    )
                        except Exception as retry_exc:
                            logger.warning("[%s] deep-insight retry failed: %s", category, retry_exc)
            return result
        except Exception as exc:
            logger.warning("Brain analysis failed: %s", exc)
            return None
