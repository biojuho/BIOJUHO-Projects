"""
BioLinker MCP Server — Model Context Protocol 서버
기존 BioLinker FastAPI의 핵심 기능을 MCP 도구(Tool)로 노출합니다.

Usage:
    python mcp_server.py                        # stdio 모드 (Claude Desktop/Codex)
    python mcp_server.py --transport sse         # SSE 모드 (웹 클라이언트)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# ── BioLinker 모듈 경로 설정 ──
_ROOT = Path(__file__).resolve().parents[2]  # d:\AI 프로젝트
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # biolinker/

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError:
    print("ERROR: mcp 패키지가 필요합니다. pip install mcp")
    sys.exit(1)

from shared.llm import LLMPolicy, TaskTier, get_client
from services.analyzer import analyze_rfp_text
from services.vector_store import get_vector_store

log = logging.getLogger("biolinker.mcp")

# ── MCP 서버 인스턴스 ──
server = Server("biolinker-mcp")


# ══════════════════════════════════════════════════════════
# Tools
# ══════════════════════════════════════════════════════════

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="analyze_rfp",
            description="RFP(연구과제 공고) 텍스트를 분석하여 적합도 점수(S/A/B/C/D)와 강점/약점을 반환합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rfp_text": {
                        "type": "string",
                        "description": "분석할 RFP 공고 전문",
                    },
                    "user_profile": {
                        "type": "string",
                        "description": "연구팀 프로필 (선택, JSON 문자열)",
                    },
                },
                "required": ["rfp_text"],
            },
        ),
        Tool(
            name="search_rfps",
            description="키워드나 프로젝트 설명으로 관련 RFP 공고를 벡터 유사도 검색합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색 키워드 또는 프로젝트 설명",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "최대 결과 수 (기본 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="generate_proposal",
            description="RFP 분석 결과를 바탕으로 연구 제안서 초안을 생성합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rfp_text": {
                        "type": "string",
                        "description": "RFP 공고 텍스트",
                    },
                    "analysis_summary": {
                        "type": "string",
                        "description": "RFP 분석 요약 (선택)",
                    },
                },
                "required": ["rfp_text"],
            },
        ),
        Tool(
            name="health_check",
            description="BioLinker 시스템 상태를 확인합니다 (벡터 DB, LLM API, IPFS).",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "analyze_rfp":
            return await _tool_analyze_rfp(arguments)
        elif name == "search_rfps":
            return await _tool_search_rfps(arguments)
        elif name == "generate_proposal":
            return await _tool_generate_proposal(arguments)
        elif name == "health_check":
            return await _tool_health_check()
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        log.error("Tool %s failed: %s", name, e)
        return [TextContent(type="text", text=f"Error: {e}")]


# ══════════════════════════════════════════════════════════
# Tool Implementations
# ══════════════════════════════════════════════════════════

async def _tool_analyze_rfp(args: dict) -> list[TextContent]:
    rfp_text = args["rfp_text"]
    profile_str = args.get("user_profile", "{}")
    try:
        profile = json.loads(profile_str) if profile_str else {}
    except json.JSONDecodeError:
        profile = {}

    client = get_client()
    prompt = f"""다음 RFP 공고를 분석하고 적합도를 평가해주세요.

## RFP 공고
{rfp_text[:4000]}

## 연구팀 프로필
{json.dumps(profile, ensure_ascii=False)[:1000]}

## 출력 형식 (JSON)
{{"fit_score": 0-100, "fit_grade": "S/A/B/C/D", "summary": "...", "strengths": ["..."], "weaknesses": ["..."]}}"""

    resp = await client.acreate(
        tier=TaskTier.HEAVY,
        messages=[{"role": "user", "content": prompt}],
        system="RFP 적합도 분석 전문가. JSON으로만 응답.",
        policy=LLMPolicy(task_kind="json_extraction", response_mode="json"),
    )
    return [TextContent(type="text", text=resp.text)]


async def _tool_search_rfps(args: dict) -> list[TextContent]:
    query = args["query"]
    limit = args.get("limit", 5)

    try:
        vs = get_vector_store()
        results = vs.search(query, n_results=min(limit, 20))
        output = json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        output = json.dumps({"error": str(e), "message": "벡터 스토어 접근 실패"}, ensure_ascii=False)

    return [TextContent(type="text", text=output)]


async def _tool_generate_proposal(args: dict) -> list[TextContent]:
    rfp_text = args["rfp_text"]
    analysis = args.get("analysis_summary", "")

    client = get_client()
    prompt = f"""다음 RFP와 분석을 바탕으로 연구 제안서 초안을 작성해주세요.

## RFP 공고
{rfp_text[:3000]}

## 분석 요약
{analysis[:1000]}

## 요청
- 한국어로 작성
- 마크다운 형식
- 연구 목표, 방법론, 기대 효과, 예산 개요 포함"""

    resp = await client.acreate(
        tier=TaskTier.HEAVY,
        messages=[{"role": "user", "content": prompt}],
        system="연구 제안서 작성 전문가. 자연스러운 한국어로 작성.",
        policy=LLMPolicy(task_kind="grant_writing"),
        max_tokens=3000,
    )
    return [TextContent(type="text", text=resp.text)]


async def _tool_health_check() -> list[TextContent]:
    status = {"server": "running", "tools": 4}
    try:
        vs = get_vector_store()
        status["vector_store"] = f"OK ({vs.count()} documents)"
    except Exception as e:
        status["vector_store"] = f"ERROR: {e}"
    try:
        client = get_client()
        status["llm"] = f"OK (backend={client.backend})"
    except Exception as e:
        status["llm"] = f"ERROR: {e}"
    return [TextContent(type="text", text=json.dumps(status, ensure_ascii=False, indent=2))]


# ══════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
