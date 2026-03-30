"""
BioLinker - Agent Service
LLM 기반 연구 분석 및 콘텐츠 작성 서비스 (shared.llm 통합)
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from services.search_service import get_search_service
from shared.llm import LLMPolicy, TaskTier
from shared.llm import get_client as _get_llm_client
from shared.llm.models import LLMResponse

# Centralized prompt templates (packages/shared/prompts/templates/*.yaml)
try:
    from shared.prompts import get_prompt_manager as _get_pm

    _pm = _get_pm()
    RESEARCH_SYSTEM_PROMPT = _pm.render("biolinker_research")
    CONTENT_PUBLISHER_PROMPT = _pm.render("biolinker_publisher")
    LITERATURE_REVIEW_SYSTEM_PROMPT = _pm.render("biolinker_lit_review")
except Exception:
    # Fallback: inline defaults if prompt templates unavailable
    RESEARCH_SYSTEM_PROMPT = "당신은 수석 AI 연구원입니다. 심도 있는 연구 리포트를 작성하세요."
    CONTENT_PUBLISHER_PROMPT = "당신은 전문 콘텐츠 퍼블리셔입니다. 요청 형식: {format_type}"
    LITERATURE_REVIEW_SYSTEM_PROMPT = "당신은 수석 의학/과학 문헌 리뷰어입니다."


@dataclass(frozen=True)
class RequestLocaleContext:
    """Locale defaults derived from request headers."""

    locale: str = "ko-KR"
    output_language: str = "ko"
    input_language: str = "auto"


class AgentService:
    """Agentic AI Service Provider (shared.llm 통합, 자동 폴백 + 비용 추적)"""

    def __init__(self) -> None:
        self.search_service = get_search_service()
        self._client = _get_llm_client()
        logger.info("agent_service_initialized", bridge="shared.llm")

    async def _call_llm(
        self,
        system_instruction: str,
        user_prompt: str,
        *,
        tier: TaskTier = TaskTier.MEDIUM,
        policy: LLMPolicy,
    ) -> LLMResponse:
        return await self._client.acreate(
            tier=tier,
            max_tokens=4000,
            system=system_instruction,
            messages=[{"role": "user", "content": user_prompt}],
            policy=policy,
        )

    async def perform_deep_research(
        self,
        topic: str,
        locale_context: RequestLocaleContext,
        max_depth: int = 2,
    ) -> dict[str, Any]:
        logger.info("deep_research_start", topic=topic, max_depth=max_depth)
        queries = await self._generate_search_queries(topic, locale_context)

        search_results = []
        for query in queries[: max(3, max_depth + 1)]:
            results = self.search_service.search(query, max_results=3)
            search_results.extend(results)
            await asyncio.sleep(1)

        report_payload = await self.synthesize_research(topic, search_results, locale_context)
        return {
            "topic": topic,
            "queries": queries,
            "results_count": len(search_results),
            "report": report_payload["report"],
            "sources": [item.get("href") for item in search_results],
            "meta": report_payload["meta"],
        }

    async def _generate_search_queries(
        self,
        topic: str,
        locale_context: RequestLocaleContext,
    ) -> list[str]:
        sys_prompt = "You are a research assistant. Output ONLY a valid JSON array of 3 to 5 search queries."
        user_prompt = (
            f"주제 '{topic}'에 대한 심층 조사를 위해 검색 쿼리 3~5개를 JSON 배열로 생성하세요. "
            "한국어, 영어, 중국어 키워드를 적절히 혼합해도 됩니다. 예: "
            '["query1", "query2"]'
        )
        response = await self._call_llm(
            sys_prompt,
            user_prompt,
            tier=TaskTier.LIGHTWEIGHT,
            policy=self._build_policy(
                locale_context,
                task_kind="search_query_generation",
                output_language="multilingual",
                enforce_korean_output=False,
                response_mode="json",
                preserve_source=topic,
            ),
        )
        parsed = self._parse_json_payload(response.text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()][:5] or [topic]
        return [topic, f"{topic} review", f"{topic} 中国 研究", f"{topic} 한국 연구"]

    async def synthesize_research(
        self,
        topic: str,
        context: list[dict[str, Any]],
        locale_context: RequestLocaleContext,
    ) -> dict[str, Any]:
        context_str = self._build_context_block(context)
        response = await self._call_llm(
            RESEARCH_SYSTEM_PROMPT,
            f"주제: {topic}\n\n수집된 검색 자료:\n{context_str}",
            tier=TaskTier.HEAVY,
            policy=self._build_policy(
                locale_context,
                task_kind="analysis",
                preserve_source=topic,
            ),
        )
        return {"report": response.text, "meta": self._response_meta(response)}

    async def write_content(
        self,
        topic: str,
        raw_text: str,
        locale_context: RequestLocaleContext,
        format_type: str = "blog_post",
    ) -> dict[str, Any]:
        system_prompt = CONTENT_PUBLISHER_PROMPT.replace("{format_type}", format_type)
        task_kind = "summary" if format_type in {"summary", "presentation"} else "grant_writing"
        response = await self._call_llm(
            system_prompt,
            f"주제: {topic}\n형식: {format_type}\n\n원천 데이터:\n{raw_text[:15000]}",
            tier=TaskTier.MEDIUM,
            policy=self._build_policy(
                locale_context,
                task_kind=task_kind,
                preserve_source=f"{topic}\n{raw_text[:2000]}",
            ),
        )
        return {"content": response.text, "meta": self._response_meta(response)}

    async def analyze_youtube_video(
        self,
        video_url: str,
        locale_context: RequestLocaleContext,
        query: str = "영상 내용을 요약해줘",
    ) -> dict[str, Any]:
        logger.info("youtube_analysis_start", video_url=video_url)
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            return {"error": "youtube_transcript_api 라이브러리가 설치되지 않았습니다."}

        video_id = self._extract_video_id(video_url)
        if not video_id:
            return {"error": "유효하지 않은 YouTube URL입니다."}

        try:
            transcript_list = YouTubeTranscriptApi().fetch(
                video_id,
                languages=["ko", "en", "zh-Hans", "zh-Hant", "zh"],
            )
            full_text = " ".join(item["text"] for item in transcript_list)
        except Exception as exc:
            return {"error": f"자막을 가져오지 못했습니다: {exc}"}

        response = await self._call_llm(
            "당신은 YouTube 영상 분석가입니다. 자막을 바탕으로 정확하게 답변하세요.",
            f"질문/요청: {query}\n\n자막 데이터:\n{full_text[:20000]}",
            tier=TaskTier.MEDIUM,
            policy=self._build_policy(
                locale_context,
                task_kind="youtube_longform",
                preserve_source=f"{query}\n{full_text[:3000]}",
            ),
        )
        return {
            "video_id": video_id,
            "query": query,
            "analysis": response.text,
            "transcript_preview": full_text[:500] + ("..." if len(full_text) > 500 else ""),
            "meta": self._response_meta(response),
        }

    async def conduct_literature_review(
        self,
        topic: str,
        locale_context: RequestLocaleContext,
    ) -> dict[str, Any]:
        logger.info("literature_review_start", topic=topic)
        query_response = await self._call_llm(
            "You are a research assistant. Output ONLY a JSON array.",
            (
                f"주제 '{topic}'에 대한 체계적인 문헌 고찰을 위해 PICO 분석에 기반한 검색 쿼리 3개를 JSON 배열로 주세요. "
                '예: ["CRISPR sickle cell", "gene therapy SCD"]'
            ),
            tier=TaskTier.LIGHTWEIGHT,
            policy=self._build_policy(
                locale_context,
                task_kind="search_query_generation",
                output_language="multilingual",
                enforce_korean_output=False,
                response_mode="json",
                preserve_source=topic,
            ),
        )

        parsed_queries = self._parse_json_payload(query_response.text)
        queries = (
            [str(item).strip() for item in parsed_queries if str(item).strip()][:3]
            if isinstance(parsed_queries, list)
            else []
        )
        if not queries:
            queries = [topic, f"{topic} review", f"{topic} clinical trial"]

        search_results = []
        for query in queries[:3]:
            search_results.extend(self.search_service.search(query, max_results=4))
            await asyncio.sleep(1)

        context_str = self._build_context_block(search_results)
        response = await self._call_llm(
            LITERATURE_REVIEW_SYSTEM_PROMPT,
            f"연구 주제: {topic}\n\n검색된 문헌 데이터:\n{context_str[:25000]}",
            tier=TaskTier.HEAVY,
            policy=self._build_policy(
                locale_context,
                task_kind="literature_review",
                preserve_source=topic,
            ),
        )
        unique_sources = []
        seen_urls = set()
        for item in search_results:
            url = item.get("href")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_sources.append(url)
        return {
            "topic": topic,
            "queries": queries,
            "results_count": len(unique_sources),
            "report": response.text,
            "meta": self._response_meta(response),
        }

    def _build_policy(
        self,
        locale_context: RequestLocaleContext,
        *,
        task_kind: str,
        preserve_source: str = "",
        output_language: str | None = None,
        enforce_korean_output: bool = True,
        response_mode: str = "text",
    ) -> LLMPolicy:
        return LLMPolicy(
            locale=locale_context.locale,
            input_language=locale_context.input_language,
            output_language=output_language or locale_context.output_language,
            task_kind=task_kind,
            enforce_korean_output=enforce_korean_output,
            allow_source_quotes=task_kind in {"analysis", "literature_review", "youtube_longform"},
            preserve_terms=self._extract_preserve_terms(preserve_source),
            response_mode=response_mode,
        )

    def _response_meta(self, response: LLMResponse) -> dict[str, Any]:
        return {
            "backend": response.backend,
            "model": response.model,
            "bridge_applied": response.bridge_meta.bridge_applied,
            "quality_flags": response.bridge_meta.quality_flags,
            "output_language": response.policy.output_language,
            "detected_input_language": response.bridge_meta.detected_input_language,
            "detected_output_language": response.bridge_meta.detected_output_language,
            "fallback_reason": response.bridge_meta.fallback_reason,
            "task_kind": response.policy.task_kind,
            "latency_ms": round(response.latency_ms, 1),
            "cost_usd": response.cost_usd,
        }

    @staticmethod
    def _extract_preserve_terms(source: str) -> list[str]:
        terms = []
        for match in re.findall(r"\b[A-Z][A-Z0-9-]{1,12}\b", source or ""):
            if match not in terms:
                terms.append(match)
        return terms[:12]

    @staticmethod
    def _parse_json_payload(text: str) -> Any:
        candidates = [text]
        match = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", text)
        if match:
            candidates.insert(0, match.group(1))
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        return None

    @staticmethod
    def _build_context_block(context: list[dict[str, Any]]) -> str:
        seen_urls = set()
        lines = []
        index = 1
        for item in context:
            url = item.get("href")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            lines.append(
                f"[{index}] {item.get('title', 'No Title')}\n"
                f"URL: {url or 'N/A'}\n"
                f"Summary: {item.get('body', '')}\n"
            )
            index += 1
        return "\n".join(lines)

    @staticmethod
    def _extract_video_id(video_url: str) -> str | None:
        if "v=" in video_url:
            return video_url.split("v=")[1].split("&")[0]
        if "youtu.be/" in video_url:
            return video_url.split("youtu.be/")[1].split("?")[0]
        return None


_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
