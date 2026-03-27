"""
getdaytrends — NotebookLM Bridge
=================================
트렌드 분석 결과를 Google NotebookLM에 자동 통합.

주요 기능:
- 고바이럴 트렌드 → NotebookLM 노트북 자동 생성
- 관련 URL(뉴스/소셜) → 소스 자동 추가
- AI 기반 심층 분석 (ask)
- 오디오/슬라이드/마인드맵 등 콘텐츠 자동 생성

의존성: notebooklm-py (pip install notebooklm-py)
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger as log

# notebooklm-py lazy import (설치되지 않은 환경에서도 에러 없이 동작)
try:
    from notebooklm import NotebookLMClient  # type: ignore
    NOTEBOOKLM_AVAILABLE = True
except ImportError:
    NOTEBOOKLM_AVAILABLE = False
    NotebookLMClient = None


# ──────────────────────────────────────────────────
#  Configuration
# ──────────────────────────────────────────────────

# NotebookLM 통합을 활성화할 최소 바이럴 점수
DEFAULT_MIN_VIRAL_SCORE = 75

# 생성할 콘텐츠 유형 (기본값)
DEFAULT_CONTENT_TYPES = ["audio"]

# 오디오 생성 시 기본 지시문
DEFAULT_AUDIO_INSTRUCTIONS = "한국어로 핵심 내용을 2분 브리핑으로 요약해줘"

# 다운로드 출력 디렉토리
DEFAULT_OUTPUT_DIR = Path("./notebooklm_output")


# ──────────────────────────────────────────────────
#  Core Bridge
# ──────────────────────────────────────────────────

async def check_availability() -> bool:
    """NotebookLM 연동 가능 여부 확인."""
    if not NOTEBOOKLM_AVAILABLE:
        log.debug("[NotebookLM] notebooklm-py 미설치 — 연동 비활성화")
        return False
    try:
        async with await NotebookLMClient.from_storage() as client:
            notebooks = await client.notebooks.list()
            log.debug(f"[NotebookLM] 인증 OK — {len(notebooks)}개 기존 노트북")
            return True
    except Exception as e:
        log.warning(f"[NotebookLM] 인증 실패 — 연동 비활성화: {e}")
        return False


async def trend_to_notebook(
    keyword: str,
    urls: list[str],
    viral_score: int = 0,
    category: str = "기타",
    context_text: str = "",
    content_types: Optional[list[str]] = None,
    audio_instructions: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> dict:
    """
    단일 트렌드를 NotebookLM 노트북으로 변환.

    Args:
        keyword: 트렌드 키워드
        urls: 관련 URL 리스트 (뉴스, 소셜 등)
        viral_score: 바이럴 점수  
        category: 카테고리
        context_text: 추가 컨텍스트 텍스트 (소셜 인사이트 등)
        content_types: 생성할 콘텐츠 유형 (audio, slide-deck, mind-map 등)
        audio_instructions: 오디오 생성 시 지시문
        output_dir: 다운로드 출력 디렉토리

    Returns:
        dict: {
            "notebook_id": str,
            "source_ids": list[str],
            "summary": str,
            "artifacts": dict[str, str],  # type → artifact_id
        }
    """
    if not NOTEBOOKLM_AVAILABLE:
        raise RuntimeError("notebooklm-py가 설치되지 않았습니다")

    content_types = content_types or DEFAULT_CONTENT_TYPES
    audio_instructions = audio_instructions or DEFAULT_AUDIO_INSTRUCTIONS
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    result = {
        "notebook_id": "",
        "source_ids": [],
        "summary": "",
        "artifacts": {},
    }

    async with await NotebookLMClient.from_storage() as client:
        # 1. 노트북 생성
        title = f"[{category}] {keyword} ({today})"
        nb = await client.notebooks.create(title)
        result["notebook_id"] = nb.id
        log.info(f"[NotebookLM] 노트북 생성: '{title}' ({nb.id[:8]}...)")

        # 2. URL 소스 추가 (최대 10개 — API 부하 방지)
        added_urls = 0
        for url in urls[:10]:
            try:
                source = await client.sources.add_url(nb.id, url, wait=True)
                result["source_ids"].append(source.id)
                added_urls += 1
            except Exception as e:
                log.warning(f"[NotebookLM] 소스 추가 실패 ({url[:50]}): {e}")
        log.info(f"[NotebookLM] 소스 {added_urls}/{len(urls)}개 추가 완료")

        # 3. 컨텍스트 텍스트를 노트로 추가
        if context_text and context_text.strip():
            try:
                await client.notes.create(
                    nb.id,
                    title=f"컨텍스트: {keyword}",
                    content=context_text[:5000],  # NotebookLM 노트 길이 제한
                )
                log.debug(f"[NotebookLM] 컨텍스트 노트 추가 ({len(context_text)}자)")
            except Exception as e:
                log.debug(f"[NotebookLM] 컨텍스트 노트 추가 실패 (무시): {e}")

        # 4. AI 요약 요청
        if result["source_ids"]:
            try:
                ask_result = await client.chat.ask(
                    nb.id,
                    f"'{keyword}'에 대한 핵심 인사이트 3가지와 "
                    f"소셜 미디어 콘텐츠 앵글 2가지를 한국어로 정리해줘"
                )
                result["summary"] = ask_result.answer
                log.info(f"[NotebookLM] AI 요약 완료 ({len(ask_result.answer)}자)")
            except Exception as e:
                log.warning(f"[NotebookLM] AI 요약 실패: {e}")

        # 5. 콘텐츠 생성 (비동기 — 생성 시작만, 완료 대기는 선택적)
        for ctype in content_types:
            try:
                artifact_id = await _generate_content(
                    client, nb.id, keyword, ctype, audio_instructions
                )
                if artifact_id:
                    result["artifacts"][ctype] = artifact_id
                    log.info(f"[NotebookLM] {ctype} 생성 시작: {artifact_id[:8]}...")
            except Exception as e:
                log.warning(f"[NotebookLM] {ctype} 생성 실패: {e}")

    return result


async def _generate_content(
    client,
    notebook_id: str,
    keyword: str,
    content_type: str,
    audio_instructions: str,
) -> Optional[str]:
    """콘텐츠 유형별 생성 시작. artifact_id 반환."""
    if content_type == "audio":
        status = await client.artifacts.generate_audio(
            notebook_id,
            instructions=audio_instructions,
        )
        return status.artifact_id if hasattr(status, 'artifact_id') else str(status)

    elif content_type == "slide-deck":
        status = await client.artifacts.generate_slide_deck(notebook_id)
        return status.artifact_id if hasattr(status, 'artifact_id') else str(status)

    elif content_type == "mind-map":
        status = await client.artifacts.generate_mind_map(notebook_id)
        return status.artifact_id if hasattr(status, 'artifact_id') else str(status)

    elif content_type == "quiz":
        status = await client.artifacts.generate_quiz(notebook_id)
        return status.artifact_id if hasattr(status, 'artifact_id') else str(status)

    elif content_type == "report":
        status = await client.artifacts.generate_report(
            notebook_id, report_format="briefing-doc"
        )
        return status.artifact_id if hasattr(status, 'artifact_id') else str(status)

    elif content_type == "infographic":
        # NotebookLM API requires explicit style/orientation —
        # omitting them causes null response and generation failure.
        from notebooklm.rpc.types import (
            InfographicOrientation,
            InfographicDetail,
            InfographicStyle,
        )
        status = await client.artifacts.generate_infographic(
            notebook_id,
            language="ko",
            instructions=f"'{keyword}'의 핵심 데이터와 인사이트를 시각적으로 정리",
            orientation=InfographicOrientation.PORTRAIT,
            detail_level=InfographicDetail.STANDARD,
            style=InfographicStyle.PROFESSIONAL,
        )
        return status.task_id if status.task_id else str(status)

    else:
        log.warning(f"[NotebookLM] 미지원 콘텐츠 유형: {content_type}")
        return None


# ──────────────────────────────────────────────────
#  Content Factory — 멀티포맷 동시 생산
# ──────────────────────────────────────────────────

async def content_factory(
    keyword: str,
    urls: list[str],
    category: str = "기타",
    context_text: str = "",
) -> dict:
    """
    트렌드 1개에서 인포그래픽 + 브리핑 리포트 + 트윗 초안을 동시 생산.

    Returns:
        {
            "notebook_id": str,
            "source_count": int,
            "summary": str,           # AI 딥리서치 요약
            "tweet_draft": str,        # 트윗 초안 (280자 이내)
            "infographic_id": str,     # 인포그래픽 artifact ID
            "report_id": str,          # 브리핑 리포트 artifact ID
        }
    """
    if not NOTEBOOKLM_AVAILABLE:
        raise RuntimeError("notebooklm-py가 설치되지 않았습니다")

    from notebooklm.rpc.types import (
        InfographicOrientation,
        InfographicDetail,
        InfographicStyle,
    )

    today = datetime.now().strftime("%Y-%m-%d")
    result = {
        "notebook_id": "",
        "source_count": 0,
        "summary": "",
        "tweet_draft": "",
        "infographic_id": "",
        "report_id": "",
    }

    async with await NotebookLMClient.from_storage() as client:
        # 1. 노트북 생성
        title = f"[{category}] {keyword} ({today})"
        nb = await client.notebooks.create(title)
        result["notebook_id"] = nb.id
        log.info(f"[ContentFactory] 노트북 생성: '{title}'")

        # 2. URL 소스 추가
        for url in urls[:10]:
            try:
                await client.sources.add_url(nb.id, url, wait=True)
                result["source_count"] += 1
            except Exception as e:
                log.warning(f"[ContentFactory] 소스 추가 실패: {e}")

        # 3. 컨텍스트 노트
        if context_text.strip():
            try:
                await client.notes.create(
                    nb.id,
                    title=f"컨텍스트: {keyword}",
                    content=context_text[:5000],
                )
            except Exception:
                pass

        # 4. AI 딥리서치 — 인사이트 + 트윗 초안 동시 요청
        try:
            insight = await client.chat.ask(
                nb.id,
                f"'{keyword}'에 대한 핵심 인사이트 3가지와 "
                f"소셜 미디어 콘텐츠 앵글 2가지를 한국어로 정리해줘",
            )
            result["summary"] = insight.answer
            log.info(f"[ContentFactory] 인사이트 완료 ({len(insight.answer)}자)")
        except Exception as e:
            log.warning(f"[ContentFactory] 인사이트 실패: {e}")

        try:
            tweet = await client.chat.ask(
                nb.id,
                f"'{keyword}'에 대해 한국어로 트위터/X 포스트 1개를 작성해줘. "
                f"조건: 280자 이내, 이모지 2-3개 포함, 해시태그 2개 포함, "
                f"호기심을 끄는 톤으로",
            )
            result["tweet_draft"] = tweet.answer.strip()
            log.info(f"[ContentFactory] 트윗 초안 완료")
        except Exception as e:
            log.warning(f"[ContentFactory] 트윗 초안 실패: {e}")

        # 5. 인포그래픽 + 브리핑 리포트 동시 생성
        try:
            info_status = await client.artifacts.generate_infographic(
                nb.id,
                language="ko",
                instructions=f"'{keyword}'의 핵심 데이터와 인사이트를 시각적으로 정리",
                orientation=InfographicOrientation.PORTRAIT,
                detail_level=InfographicDetail.STANDARD,
                style=InfographicStyle.PROFESSIONAL,
            )
            result["infographic_id"] = info_status.task_id or ""
            log.info(f"[ContentFactory] 인포그래픽 생성 시작")
        except Exception as e:
            log.warning(f"[ContentFactory] 인포그래픽 실패: {e}")

        try:
            report_status = await client.artifacts.generate_report(
                nb.id, report_format="briefing-doc"
            )
            rid = report_status.task_id if hasattr(report_status, "task_id") else ""
            result["report_id"] = rid or ""
            log.info(f"[ContentFactory] 브리핑 리포트 생성 시작")
        except Exception as e:
            log.warning(f"[ContentFactory] 리포트 실패: {e}")

    return result


# ──────────────────────────────────────────────────
#  Pipeline Integration
# ──────────────────────────────────────────────────

async def enrich_trends_with_notebooklm(
    quality_trends: list,
    contexts: dict,
    min_viral_score: int = DEFAULT_MIN_VIRAL_SCORE,
    content_types: Optional[list[str]] = None,
    max_notebooks: int = 3,
) -> list[dict]:
    """
    파이프라인의 스코어링 후 단계에서 호출.
    고바이럴 트렌드를 NotebookLM에 자동 등록하고 심층 분석 생성.

    Args:
        quality_trends: 스코어링/필터링된 트렌드 리스트 (ScoredTrend 객체)
        contexts: {keyword: TrendContext} 매핑
        min_viral_score: NotebookLM 통합 최소 바이럴 점수
        content_types: 생성할 콘텐츠 유형
        max_notebooks: 최대 생성 노트북 수 (API 부하 방지)

    Returns:
        list[dict]: 생성된 노트북 정보 리스트
    """
    if not NOTEBOOKLM_AVAILABLE:
        return []

    # 바이럴 점수 기준 상위 트렌드 선택
    high_viral = [
        t for t in quality_trends
        if getattr(t, "viral_potential", 0) >= min_viral_score
    ][:max_notebooks]

    if not high_viral:
        log.debug(f"[NotebookLM] 바이럴≥{min_viral_score} 트렌드 없음 — 스킵")
        return []

    log.info(
        f"[NotebookLM] 고바이럴 {len(high_viral)}개 트렌드 → 노트북 생성 시작"
    )

    results = []
    for trend in high_viral:
        keyword = getattr(trend, "keyword", "") or getattr(trend, "name", "")
        ctx = contexts.get(keyword) or contexts.get(getattr(trend, "name", ""))

        # 컨텍스트에서 URL 추출
        urls = _extract_urls_from_context(ctx) if ctx else []

        # 컨텍스트 텍스트 병합
        context_text = ""
        if ctx:
            context_text = ctx.to_combined_text() if hasattr(ctx, "to_combined_text") else str(ctx)

        try:
            result = await trend_to_notebook(
                keyword=keyword,
                urls=urls,
                viral_score=getattr(trend, "viral_potential", 0),
                category=getattr(trend, "category", "기타"),
                context_text=context_text,
                content_types=content_types,
            )
            results.append(result)
        except Exception as e:
            log.error(f"[NotebookLM] '{keyword}' 노트북 생성 실패: {e}")

    return results


def _extract_urls_from_context(ctx) -> list[str]:
    """TrendContext 객체에서 URL들을 추출."""
    urls = []

    # sources 속성에서 URL 추출
    sources = getattr(ctx, "sources", [])
    if isinstance(sources, list):
        for s in sources:
            if isinstance(s, str) and s.startswith("http"):
                urls.append(s)
            elif isinstance(s, dict) and "url" in s:
                urls.append(s["url"])

    # news_insight에서 URL 추출
    news = getattr(ctx, "news_insight", "")
    if news:
        import re
        found = re.findall(r'https?://[^\s<>"\']+', str(news))
        urls.extend(found)

    # 중복 제거 및 순서 보존
    seen = set()
    unique = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)

    return unique


# ──────────────────────────────────────────────────
#  Notion Auto-Publisher
# ──────────────────────────────────────────────────

async def publish_to_notion(
    factory_result: dict,
    notion_api_key: str,
    database_id: str,
) -> dict:
    """
    콘텐츠 팩토리 결과를 Notion 데이터베이스에 자동 발행.

    Returns:
        {"notion_page_id": str, "notion_url": str}
    """
    import httpx

    headers = {
        "Authorization": f"Bearer {notion_api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    # 제목에서 키워드 추출
    nb_id = factory_result.get("notebook_id", "")
    summary = factory_result.get("summary", "")[:2000]
    tweet = factory_result.get("tweet_draft", "")
    infographic_id = factory_result.get("infographic_id", "")

    # DB 스키마 조회 → title 필드명 동적 감지
    async with httpx.AsyncClient() as http:
        db_resp = await http.get(
            f"https://api.notion.com/v1/databases/{database_id}",
            headers=headers,
            timeout=15,
        )
        db_resp.raise_for_status()
        db_schema = db_resp.json()

    # title 필드 이름 찾기 (기본: "Name")
    title_field = "Name"
    db_props = db_schema.get("properties", {})
    for prop_name, prop_info in db_props.items():
        if isinstance(prop_info, dict) and prop_info.get("type") == "title":
            title_field = prop_name
            break

    # 기본 properties: title만 확실히 설정
    properties = {
        title_field: {
            "title": [{"text": {"content": f"📊 {factory_result.get('keyword', 'Analysis')}"}}]
        },
    }
    # select 필드 있으면 추가
    if "Status" in db_props:
        properties["Status"] = {"select": {"name": "자동생성"}}
    if "Category" in db_props:
        properties["Category"] = {"select": {"name": factory_result.get("category", "기타")}}

    # Notion 페이지 생성
    page_data = {
        "parent": {"database_id": database_id},
        "properties": properties,
        "children": [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "🧠 AI 인사이트"}}]},
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": summary}}]},
            },
            {
                "object": "block",
                "type": "divider",
                "divider": {},
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "🐦 트윗 초안"}}]},
            },
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"emoji": "🐦"},
                    "rich_text": [{"text": {"content": tweet}}],
                },
            },
            {
                "object": "block",
                "type": "divider",
                "divider": {},
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "🔗 리소스"}}]},
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"text": {"content": f"NotebookLM: https://notebooklm.google.com/notebook/{nb_id}"}}],
                },
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"text": {"content": f"인포그래픽 ID: {infographic_id}"}}],
                },
            },
        ],
    }

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=page_data,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

    page_id = data["id"]
    notion_url = data.get("url", f"https://notion.so/{page_id.replace('-', '')}")
    log.info(f"[Notion] 페이지 생성 완료: {notion_url}")

    return {"notion_page_id": page_id, "notion_url": notion_url}




# -- backward-compat re-exports from notebooklm_research --
from notebooklm_research import (  # noqa: F401
    research_tool,
    analyze_bio_company,
)
