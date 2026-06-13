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

from datetime import datetime
from pathlib import Path

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
    content_types: list[str] | None = None,
    audio_instructions: str | None = None,
    output_dir: Path | None = None,
) -> dict:
    """Convert one trend into a NotebookLM notebook and optional artifacts."""
    _ensure_notebooklm_available()
    content_types = content_types or DEFAULT_CONTENT_TYPES
    audio_instructions = audio_instructions or DEFAULT_AUDIO_INSTRUCTIONS
    _ensure_output_dir(output_dir or DEFAULT_OUTPUT_DIR)

    result = _empty_notebook_result()
    async with await NotebookLMClient.from_storage() as client:
        notebook = await _create_trend_notebook(client, keyword, category)
        result["notebook_id"] = notebook.id
        result["source_ids"] = await _add_notebook_sources(client, notebook.id, urls)
        await _add_context_note(client, notebook.id, keyword, context_text)
        result["summary"] = await _ask_notebook_summary(client, notebook.id, keyword, bool(result["source_ids"]))
        result["artifacts"] = await _generate_notebook_artifacts(
            client,
            notebook.id,
            keyword,
            content_types,
            audio_instructions,
        )
    return result


def _ensure_notebooklm_available() -> None:
    if not NOTEBOOKLM_AVAILABLE:
        raise RuntimeError("notebooklm-py가 설치되지 않았습니다")


def _ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def _empty_notebook_result() -> dict:
    return {
        "notebook_id": "",
        "source_ids": [],
        "summary": "",
        "artifacts": {},
    }


async def _create_trend_notebook(client, keyword: str, category: str) -> object:
    title = f"[{category}] {keyword} ({datetime.now().strftime('%Y-%m-%d')})"
    notebook = await client.notebooks.create(title)
    log.info(f"[NotebookLM] 노트북 생성: '{title}' ({notebook.id[:8]}...)")
    return notebook


async def _add_notebook_sources(client, notebook_id: str, urls: list[str]) -> list[str]:
    source_ids: list[str] = []
    for url in urls[:10]:
        try:
            source = await client.sources.add_url(notebook_id, url, wait=True)
            source_ids.append(source.id)
        except Exception as e:
            log.warning(f"[NotebookLM] 소스 추가 실패 ({url[:50]}): {e}")
    log.info(f"[NotebookLM] 소스 {len(source_ids)}/{len(urls)}개 추가 완료")
    return source_ids


async def _add_context_note(client, notebook_id: str, keyword: str, context_text: str) -> None:
    if not context_text or not context_text.strip():
        return
    try:
        await client.notes.create(
            notebook_id,
            title=f"컨텍스트: {keyword}",
            content=context_text[:5000],
        )
        log.debug(f"[NotebookLM] 컨텍스트 노트 추가 ({len(context_text)}자)")
    except Exception as e:
        log.debug(f"[NotebookLM] 컨텍스트 노트 추가 실패 (무시): {e}")


async def _ask_notebook_summary(client, notebook_id: str, keyword: str, has_sources: bool) -> str:
    if not has_sources:
        return ""
    try:
        ask_result = await client.chat.ask(
            notebook_id,
            f"'{keyword}'에 대한 핵심 인사이트 3가지와 소셜 미디어 콘텐츠 각도 2가지를 한국어로 정리해줘",
        )
        log.info(f"[NotebookLM] AI 요약 완료 ({len(ask_result.answer)}자)")
        return ask_result.answer
    except Exception as e:
        log.warning(f"[NotebookLM] AI 요약 실패: {e}")
        return ""


async def _generate_notebook_artifacts(
    client,
    notebook_id: str,
    keyword: str,
    content_types: list[str],
    audio_instructions: str,
) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for ctype in content_types:
        try:
            artifact_id = await _generate_content(client, notebook_id, keyword, ctype, audio_instructions)
            if artifact_id:
                artifacts[ctype] = artifact_id
                log.info(f"[NotebookLM] {ctype} 생성 시작: {artifact_id[:8]}...")
        except Exception as e:
            log.warning(f"[NotebookLM] {ctype} 생성 실패: {e}")
    return artifacts

_STANDARD_ARTIFACT_GENERATORS = {
    "slide-deck": ("generate_slide_deck", {}),
    "mind-map": ("generate_mind_map", {}),
    "quiz": ("generate_quiz", {}),
    "report": ("generate_report", {"report_format": "briefing-doc"}),
}


def _artifact_identifier(status) -> str:
    return getattr(status, "artifact_id", None) or getattr(status, "task_id", None) or str(status)


async def _generate_standard_artifact(
    client,
    notebook_id: str,
    content_type: str,
    audio_instructions: str,
) -> object:
    if content_type == "audio":
        return await client.artifacts.generate_audio(notebook_id, instructions=audio_instructions)

    generator = _STANDARD_ARTIFACT_GENERATORS.get(content_type)
    if generator is None:
        return None
    method_name, kwargs = generator
    method = getattr(client.artifacts, method_name)
    return await method(notebook_id, **kwargs)


async def _generate_infographic_artifact(client, notebook_id: str, keyword: str) -> object:
    # NotebookLM API requires explicit style/orientation; omitting them can return null.
    from notebooklm.rpc.types import (
        InfographicDetail,
        InfographicOrientation,
        InfographicStyle,
    )

    return await client.artifacts.generate_infographic(
        notebook_id,
        language="ko",
        instructions=f"'{keyword}' core data and insights as a visual summary",
        orientation=InfographicOrientation.PORTRAIT,
        detail_level=InfographicDetail.STANDARD,
        style=InfographicStyle.PROFESSIONAL,
    )


async def _generate_content(
    client,
    notebook_id: str,
    keyword: str,
    content_type: str,
    audio_instructions: str,
) -> str | None:
    """Start NotebookLM artifact generation and return its artifact or task id."""
    if content_type == "infographic":
        status = await _generate_infographic_artifact(client, notebook_id, keyword)
        return _artifact_identifier(status)

    status = await _generate_standard_artifact(client, notebook_id, content_type, audio_instructions)
    if status is None:
        log.warning(f"[NotebookLM] unsupported content type: {content_type}")
        return None
    return _artifact_identifier(status)

# ──────────────────────────────────────────────────
#  Content Factory — 멀티포맷 동시 생산
# ──────────────────────────────────────────────────


def _content_factory_result() -> dict:
    return {
        "notebook_id": "",
        "source_count": 0,
        "summary": "",
        "tweet_draft": "",
        "infographic_id": "",
        "report_id": "",
    }


async def _add_content_factory_sources(client, notebook_id: str, urls: list[str]) -> int:
    source_count = 0
    for url in urls[:10]:
        try:
            await client.sources.add_url(notebook_id, url, wait=True)
            source_count += 1
        except Exception as e:
            log.warning(f"[ContentFactory] source add failed: {e}")
    return source_count


async def _add_content_factory_context_note(client, notebook_id: str, keyword: str, context_text: str) -> None:
    if not context_text.strip():
        return
    try:
        await client.notes.create(
            notebook_id,
            title=f"Context: {keyword}",
            content=context_text[:5000],
        )
    except Exception as e:
        log.warning(f"[ContentFactory] context note failed: {e}")


async def _ask_content_factory_summary(client, notebook_id: str, keyword: str) -> str:
    try:
        insight = await client.chat.ask(
            notebook_id,
            f"Summarize three key insights about '{keyword}' and two social media content angles in Korean.",
        )
        return insight.answer
    except Exception as e:
        log.warning(f"[ContentFactory] insight generation failed: {e}")
        return ""


async def _ask_content_factory_tweet(client, notebook_id: str, keyword: str) -> str:
    try:
        tweet = await client.chat.ask(
            notebook_id,
            f"Write one engaging Korean X post about '{keyword}' under 280 characters with 2-3 emoji and 2 hashtags.",
        )
        return tweet.answer.strip()
    except Exception as e:
        log.warning(f"[ContentFactory] tweet draft failed: {e}")
        return ""


async def _generate_content_factory_outputs(client, notebook_id: str, keyword: str) -> dict[str, str]:
    outputs = {"infographic_id": "", "report_id": ""}
    try:
        info_status = await _generate_infographic_artifact(client, notebook_id, keyword)
        outputs["infographic_id"] = _artifact_identifier(info_status)
        log.info("[ContentFactory] infographic generation started")
    except Exception as e:
        log.warning(f"[ContentFactory] infographic failed: {e}")

    try:
        report_status = await client.artifacts.generate_report(notebook_id, report_format="briefing-doc")
        outputs["report_id"] = _artifact_identifier(report_status)
        log.info("[ContentFactory] report generation started")
    except Exception as e:
        log.warning(f"[ContentFactory] report failed: {e}")
    return outputs


async def content_factory(
    keyword: str,
    urls: list[str],
    category: str = "기타",
    context_text: str = "",
) -> dict:
    """Produce a NotebookLM-backed summary, tweet draft, infographic, and report."""
    if not NOTEBOOKLM_AVAILABLE:
        raise RuntimeError("notebooklm-py is not installed")

    today = datetime.now().strftime("%Y-%m-%d")
    result = _content_factory_result()

    async with await NotebookLMClient.from_storage() as client:
        title = f"[{category}] {keyword} ({today})"
        nb = await client.notebooks.create(title)
        result["notebook_id"] = nb.id
        log.info(f"[ContentFactory] notebook created: '{title}'")

        result["source_count"] = await _add_content_factory_sources(client, nb.id, urls)
        await _add_content_factory_context_note(client, nb.id, keyword, context_text)
        result["summary"] = await _ask_content_factory_summary(client, nb.id, keyword)
        result["tweet_draft"] = await _ask_content_factory_tweet(client, nb.id, keyword)
        result.update(await _generate_content_factory_outputs(client, nb.id, keyword))

    return result

# ──────────────────────────────────────────────────
#  Pipeline Integration
# ──────────────────────────────────────────────────


def _notebooklm_candidate_trends(quality_trends: list, min_viral_score: int, max_notebooks: int) -> list:
    return [t for t in quality_trends if getattr(t, "viral_potential", 0) >= min_viral_score][:max_notebooks]


def _notebooklm_trend_keyword(trend) -> str:
    return getattr(trend, "keyword", "") or getattr(trend, "name", "")


def _notebooklm_context_for_trend(trend, contexts: dict) -> object:
    keyword = _notebooklm_trend_keyword(trend)
    return contexts.get(keyword) or contexts.get(getattr(trend, "name", ""))


def _notebooklm_context_text(ctx) -> str:
    if not ctx:
        return ""
    return ctx.to_combined_text() if hasattr(ctx, "to_combined_text") else str(ctx)


async def _enrich_one_trend_with_notebooklm(trend, contexts: dict, content_types: list[str] | None) -> dict | None:
    keyword = _notebooklm_trend_keyword(trend)
    ctx = _notebooklm_context_for_trend(trend, contexts)
    try:
        return await trend_to_notebook(
            keyword=keyword,
            urls=_extract_urls_from_context(ctx) if ctx else [],
            viral_score=getattr(trend, "viral_potential", 0),
            category=getattr(trend, "category", "기타"),
            context_text=_notebooklm_context_text(ctx),
            content_types=content_types,
        )
    except Exception as e:
        log.error(f"[NotebookLM] '{keyword}' notebook creation failed: {e}")
        return None


async def enrich_trends_with_notebooklm(
    quality_trends: list,
    contexts: dict,
    min_viral_score: int = DEFAULT_MIN_VIRAL_SCORE,
    content_types: list[str] | None = None,
    max_notebooks: int = 3,
) -> list[dict]:
    """Create NotebookLM notebooks for high-viral trends and return notebook metadata."""
    if not NOTEBOOKLM_AVAILABLE:
        return []

    high_viral = _notebooklm_candidate_trends(quality_trends, min_viral_score, max_notebooks)
    if not high_viral:
        log.debug(f"[NotebookLM] no trends at viral>={min_viral_score}; skipping")
        return []

    log.info(f"[NotebookLM] creating notebooks for {len(high_viral)} high-viral trends")
    results = []
    for trend in high_viral:
        result = await _enrich_one_trend_with_notebooklm(trend, contexts, content_types)
        if result:
            results.append(result)
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
        title_field: {"title": [{"text": {"content": f"📊 {factory_result.get('keyword', 'Analysis')}"}}]},
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
    analyze_bio_company,
    research_tool,
)
