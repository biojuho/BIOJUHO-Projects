"""
BioLinker - Agent Service
LLM 기반 연구 분석 및 콘텐츠 작성 서비스 (shared.llm 통합)
"""
import re
import json
import asyncio
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

# shared.llm 모듈
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))
from shared.llm import TaskTier, get_client as _get_llm_client

from services.search_service import get_search_service

# System Prompts
RESEARCH_SYSTEM_PROMPT = """당신은 수석 AI 연구원입니다.
제공된 검색 결과와 문맥을 바탕으로 심도 있는 연구 리포트를 작성해야 합니다.

## 역할
- 복잡한 정보를 구조화하여 명확하게 전달
- 사실 기반의 분석 (검색 결과 인용 필수)
- 객관적이고 전문적인 어조 유지

## 출력 형식 (Markdown)
# [주제] 심층 분석
## 요약 (Executive Summary)
## 주요 발견 (Key Findings)
## 상세 분석 (Deep Dive)
## 결론 및 전망
## 참고 문헌 (References)
"""

CONTENT_PUBLISHER_PROMPT = """당신은 전문 콘텐츠 퍼블리셔입니다.
주어진 주제와 원천 데이터(연구 내용 등)를 바탕으로 지정된 형식의 고품질 콘텐츠를 작성합니다.

## 요청 형식: {format_type}

### 1. 블로그 포스트 (Blog Post)
- 독자의 흥미를 유발하는 제목과 도입부
- SEO를 고려한 구조 (H2, H3, 리스트 활용)
- 명확한 인사이트와 행동 유도(Call to Action)

### 2. 뉴스레터 (Newsletter)
- 개인적인 어조 (안녕하세요, [이름]입니다...)
- 핵심 소식 큐레이션 및 요약
- 읽기 편한 간결한 문체

### 3. 소셜 미디어 (Social Media)
- 트위터/링크드인 스타일
- 핵심 메시지 중심의 짧은 글 (이모지 활용)
- 해시태그 포함

## 원천 데이터 처리
- 제공된 텍스트의 핵심 내용을 유지하되, 각 플랫폼/형식에 맞게 재구성하세요.
- 환각(Hallucination)을 피하고 사실에 기반하여 작성하세요.
"""

class AgentService:
    """Agentic AI Service Provider (shared.llm 통합, 자동 폴백 + 비용 추적)"""

    def __init__(self):
        self.search_service = get_search_service()
        self._client = _get_llm_client()
        print("[AgentService] Initialized with shared.llm (tier-based routing)")

    async def _call_llm(self, system_instruction: str, user_prompt: str, tier: TaskTier = TaskTier.MEDIUM) -> str:
        """shared.llm 통합 LLM 호출 (자동 폴백 + 비용 최적화)"""
        try:
            response = await self._client.acreate(
                tier=tier,
                max_tokens=4000,
                system=system_instruction,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.text
        except Exception as e:
            return f"Error: LLM call failed: {str(e)}"

    async def perform_deep_research(self, topic: str, max_depth: int = 2) -> Dict[str, Any]:
        """Deep Research Skill Execution"""
        print(f"[Agent] Starting Deep Research on: {topic}")

        # 1. Query Generation
        queries = await self._generate_search_queries(topic)
        print(f"[Agent] Generated Queries: {queries}")
        
        # 2. Search Execution
        search_results = []
        for query in queries[:3]: # Limit to top 3 queries
            results = self.search_service.search(query, max_results=3)
            search_results.extend(results)
            await asyncio.sleep(1) # Rate limit
            
        # 3. Synthesis
        report = await self.synthesize_research(topic, search_results)
        
        return {
            "topic": topic,
            "queries": queries,
            "results_count": len(search_results),
            "report": report,
            "sources": [r.get('href') for r in search_results]
        }

    async def _generate_search_queries(self, topic: str) -> List[str]:
        """주제를 검색 쿼리로 분해"""
        sys_prompt = "You are a research assistant. Output ONLY a valid JSON array of 3-5 search queries."
        user_prompt = f"주제 '{topic}'에 대한 심층 조사를 위해 필요한 영어/한국어 섞인 검색 쿼리 3개를 JSON 리스트형식으로 생성해줘. 예: [\"query1\", \"query2\"]"
        
        response = await self._call_llm(sys_prompt, user_prompt, tier=TaskTier.LIGHTWEIGHT)
        try:
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                return json.loads(match.group())
            return [topic]
        except (json.JSONDecodeError, ValueError):
            return [topic, f"{topic} trends", f"{topic} analysis"]

    async def synthesize_research(self, topic: str, context: List[Dict[str, Any]]) -> str:
        """검색 결과를 바탕으로 연구 리포트 작성"""
        context_str = ""
        seen_urls = set()
        unique_context = []
        
        for item in context:
            url = item.get('href')
            if url not in seen_urls:
                seen_urls.add(url)
                unique_context.append(item)
        
        for i, item in enumerate(unique_context, 1):
            context_str += f"[{i}] {item.get('title', 'No Title')}\nURL: {item.get('href', 'N/A')}\nSummary: {item.get('body', '')}\n\n"
            
        user_prompt = f"주제: {topic}\n\n수집된 검색 자료:\n{context_str}"
        return await self._call_llm(RESEARCH_SYSTEM_PROMPT, user_prompt, tier=TaskTier.HEAVY)

    async def write_content(self, topic: str, raw_text: str, format_type: str = "blog_post") -> str:
        """Content Publisher Skill Execution"""
        sys_prompt = CONTENT_PUBLISHER_PROMPT.replace("{format_type}", format_type)
        user_prompt = f"주제: {topic}\n형식: {format_type}\n\n원천 데이터:\n{raw_text[:15000]}"
        return await self._call_llm(sys_prompt, user_prompt)

    async def analyze_youtube_video(self, video_url: str, query: str = "Summarize the video") -> Dict[str, Any]:
        """YouTube Intelligence"""
        print(f"[Agent] Analyzing YouTube Video: {video_url}")
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            
            video_id = None
            if "v=" in video_url:
                video_id = video_url.split("v=")[1].split("&")[0]
            elif "youtu.be/" in video_url:
                video_id = video_url.split("youtu.be/")[1].split("?")[0]
            
            if not video_id:
                return {"error": "Invalid YouTube URL"}
                
            try:
                ytt_api = YouTubeTranscriptApi()
                transcript_list = ytt_api.fetch(video_id, languages=['ko', 'en'])
                full_text = " ".join([t['text'] for t in transcript_list])
            except Exception as e:
                return {"error": f"Failed to fetch transcript: {str(e)}"}
                
            system_prompt = "당신은 YouTube 영상 분석가입니다. 자막을 바탕으로 정확하게 답변하세요."
            user_prompt = f"질문/요청: {query}\n\n자막 데이터:\n{full_text[:20000]}"
            
            content = await self._call_llm(system_prompt, user_prompt)
            return {
                "video_id": video_id,
                "query": query,
                "analysis": content,
                "transcript_preview": full_text[:500] + "..."
            }
        except ImportError:
            return {"error": "youtube_transcript_api library not installed."}
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}

    async def conduct_literature_review(self, topic: str) -> Dict[str, Any]:
        """Literature Review Skill Execution"""
        print(f"[Agent] Starting Literature Review on: {topic}")

        # 1. Generate PICO-style queries
        sys_prompt = "You are a research assistant. Output ONLY a JSON array."
        user_prompt = f"주제 '{topic}'에 대한 체계적인 문헌 고찰을 위해 PICO 분석에 기반한 검색 쿼리 3개를 JSON 문자열 배열로 줘. 예: [\"CRISPR sickle cell\", \"gene therapy SCD\"]"
        
        query_res = await self._call_llm(sys_prompt, user_prompt)
        try:
            queries = []
            match = re.search(r'\[.*\]', query_res, re.DOTALL)
            if match:
                queries = json.loads(match.group())
            if not queries:
                 queries = [topic, f"{topic} review", f"{topic} clinical trial"]
        except Exception as e:
            print(f"Error generating review queries: {e}")
            queries = [topic]

        # 2. Search
        search_results = []
        for query in queries[:3]:
            results = self.search_service.search(query, max_results=4)
            search_results.extend(results)
            await asyncio.sleep(1)

        # 3. Synthesize thematic review
        review_system_prompt = """당신은 수석 의학/과학 문헌 리뷰어입니다.
개별 논문을 병렬 요약하지 말고, 반드시 **주제별(Thematic)로 종합**하세요.
주장은 검색 URL로 인용하세요 예: [1](http...). 서론/주제별분석/결론/참고문헌 포함. Markdown 포맷 필수.
"""
        context_str = ""
        seen_urls = set()
        v_idx = 1
        for item in search_results:
            url = item.get('href')
            if url not in seen_urls:
                seen_urls.add(url)
                context_str += f"[{v_idx}] {item.get('title', '')}\nURL: {url}\n내용: {item.get('body', '')}\n\n"
                v_idx += 1

        user_prompt2 = f"연구 주제: {topic}\n\n검색된 문헌 데이터:\n{context_str[:25000]}"
        content = await self._call_llm(review_system_prompt, user_prompt2)

        return {
            "topic": topic,
            "queries": queries,
            "results_count": len(seen_urls),
            "report": content
        }

# Singleton
_agent_service = None

def get_agent_service():
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
