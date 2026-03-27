"""
getdaytrends v3.0 - Viral Scoring & Trend Analysis
Claude를 활용한 바이럴 포텐셜 스코어링 + 히스토리 패턴 감지 + 트렌드 클러스터링.
async/await 기반 병렬 스코어링 + JSON structured output + 스코어 캐시 + 재시도 지원.
v3.0: 배치 스코어링(5개/호출, 비용 ~70% 절감) + sentiment/safety_flag 분석 추가.
"""

import asyncio
import json
import sqlite3



from config import AppConfig
from db import compute_fingerprint, get_cached_score
from models import MultiSourceContext, RawTrend, ScoredTrend, TrendSource
from shared.llm import LLMClient, TaskTier, get_client
from shared.llm.models import LLMPolicy
from trend_clustering import _jaccard_similarity, cluster_trends, cluster_trends_local  # noqa: F401
from trend_genealogy import (  # noqa: F401
    analyze_trend_genealogy,
    detect_trend_patterns,
    enrich_trends_with_genealogy,
)
from utils import run_async, sanitize_keyword

from loguru import logger as log

# -- 추출된 모듈 re-export (후방 호환) --
from analysis.parsing import (  # noqa: F401
    INSTRUCTOR_AVAILABLE,
    _default_scored_trend,
    _parse_json,
    _parse_json_array,
    _parse_scored_trend_from_dict,
    _score_batch_instructor,
)


# ══════════════════════════════════════════════════════
#  Scoring Prompt
# ══════════════════════════════════════════════════════

SCORING_PROMPT_TEMPLATE = """당신은 소셜 미디어 트렌드 분석 전문가입니다.
현재 시각: {current_time}

키워드: {keyword}
현재 볼륨: {volume}

수집된 실시간 데이터:
{context}

[핵심 분석 원칙]
- "왜 트렌드인지"가 아니라 "왜 지금 이 시점에 폭발했는지" 인과관계를 추론할 것
- 추상적 표현("최근 논란", "화제가 되고 있다") 절대 금지 — 구체적 사건/숫자로 설명
- 컨텍스트에 나온 실제 데이터를 근거로 분석할 것
- 키워드가 문장 조각이거나 의미 불명이면 publishable=false로 판정

다음 JSON 스키마로 정확히 응답:
{{
    "keyword": "{keyword}",
    "publishable": true,
    "publishability_reason": "게시 불가 사유 (publishable=true면 빈 문자열)",
    "corrected_keyword": "오타/약어인 경우 교정된 원본 (정상이면 빈 문자열)",
    "volume_last_24h": 1000,
    "trend_acceleration": "+10%",
    "viral_potential": 85,
    "top_insight": "가장 뜨거운 이슈 1문장",
    "why_trending": "왜 지금 이 트렌드가 뜨는지 원인 1-2문장 추론",
    "peak_status": "상승중|정점|하락중 중 하나",
    "relevance_score": 7,
    "suggested_angles": ["반직관적 앵글", "데이터 기반 앵글", "미래 예측 앵글"],
    "best_hook_starter": "타임라인에서 스크롤 멈추게 하는 첫 문장. 반드시 아래 6가지 패턴 중 하나: 숫자충격('3일 만에 2000억 증발'), 체감환산('월급 250만원 받는 사람한테'), 반전선언('이거 좋은 뉴스라고 생각하면 큰일남'), 내부자시선('이 업계에서 보기에'), 대조병치('그쪽은 축배를 드는데 이쪽은 이력서를 쓴다'), 질문도발('이거 왜 아무도 이상하다고 안 함?'). '화제가 되고 있다' 식 기자체 금지",
    "category": "연예|스포츠|정치|경제|테크|사회|국제|날씨|음식|게임|기타 중 하나",
    "sentiment": "positive|neutral|negative|harmful 중 하나",
    "safety_flag": false,
    "trigger_event": "촉발 사건/발언/발표 (시점 포함)",
    "chain_reaction": "촉발 이후 전개 과정",
    "why_now": "지금 터진 특수한 이유",
    "key_positions": ["찬성측 주장", "반대측 주장"]
}}
- publishable: 이 키워드로 의미 있는 SNS 콘텐츠를 만들 수 있으면 true. 문장 조각·의미불명이면 false
- corrected_keyword: 오타·축약어이면 교정 원본 제시. 정상이면 빈 문자열
- safety_flag=true 조건: 재난/사망/폭력/혐오/자살, 그리고 정치·외교적 갈등(반미/반일/반한) 및 페미니즘 등 특정 이념·성별 갈등 이슈 트렌드."""


# ── 배치 스코어링 프롬프트 (Phase 2: 5개/호출, 비용 ~70% 절감) ──

BATCH_SCORING_PROMPT_TEMPLATE = """당신은 소셜 미디어 트렌드 분석 전문가입니다.
현재 시각: {current_time}
아래 {n}개의 트렌드를 동시에 분석하세요.

트렌드 목록 (JSON):
{trends_json}

[핵심 분석 원칙]
1. "왜 트렌드인지"가 아니라 "왜 지금 이 시점에 폭발했는지" 인과관계를 추론할 것
2. 컨텍스트에 나온 실제 데이터(수치, 발언, 사건)를 근거로 분석할 것
3. 추상적 표현("최근 논란", "화제가 되고 있다") 절대 금지 — 구체적 사건/숫자로 설명
4. X에서 활발히 논의되기 적합한 트렌드만 높은 relevance_score 부여
5. 이미 하락세인 트렌드는 peak_status=하락중으로 표시
6. **게시 가능성(publishable)을 반드시 판단**: 아래 경우 publishable=false 처리
   - 문장 조각 (예: "아주 여리고", "그래서 결국") → 완전한 개념이 아님
   - 의미 불명 키워드 → 컨텍스트로도 뭔지 알 수 없음
   - 오타·약어 키워드 → corrected_keyword에 교정된 원본을 제시 (publishable은 true로 유지하되 교정)

[정보 정확성 원칙 — 필수]
7. **팩트 그라운딩**: why_trending, trigger_event, top_insight에는 반드시 컨텍스트에 실제로 존재하는 사건/수치/발언만 사용할 것
8. **수치 정확성**: 숫자(금액, 인원, 비율)는 컨텍스트에 나온 것만 사용. 확인 불가한 수치는 "약", "추정" 등 한정어 부착
9. **기관/인물 정확성**: 기관명, 인물명은 컨텍스트에 명시적으로 언급된 경우에만 사용. 추론으로 기관명을 만들지 말 것
10. **출처 불명 주장 금지**: "전문가들은", "관계자에 따르면" 등 출처 불명 인용은 0점. 컨텍스트에 실제 출처가 있을 때만 인용

각 트렌드에 대해 반드시 다음 JSON 배열로 응답 (순서와 개수 유지):
[
  {{
    "keyword": "원본 키워드 (변경 금지)",
    "publishable": true,
    "publishability_reason": "게시 불가 사유 (publishable=true면 빈 문자열)",
    "corrected_keyword": "오타/약어인 경우 교정된 원본 (정상이면 빈 문자열)",
    "volume_last_24h": 1000,
    "trend_acceleration": "+10%",
    "viral_potential": 85,
    "top_insight": "핵심 이슈 1문장",
    "why_trending": "왜 지금 이 트렌드가 뜨는지 원인 1-2문장 추론",
    "peak_status": "상승중|정점|하락중 중 하나",
    "relevance_score": 7,
    "suggested_angles": ["앵글1", "앵글2", "앵글3"],
    "best_hook_starter": "타임라인에서 스크롤 멈추게 하는 첫 문장 (6패턴: 숫자충격/체감환산/반전선언/내부자시선/대조병치/질문도발. 기자체 금지)",
    "category": "연예|스포츠|정치|경제|테크|사회|국제|날씨|음식|게임|기타 중 하나",
    "sentiment": "positive|neutral|negative|harmful 중 하나",
    "safety_flag": false,
    "joongyeon_kick": 80,
    "joongyeon_angle": "현상의 역설이나 반전이 담긴 단 한 문장 (없으면 빈 문자열)",
    "trigger_event": "이 트렌드를 촉발한 구체적 사건/발언/발표 (시점 포함, 예: 'OO장관 XX 발언 3시간 전')",
    "chain_reaction": "촉발 사건 이후 전개 과정 (예: '커뮤니티 확산 → 언론 보도 → 반박 성명')",
    "why_now": "과거에도 비슷한 이슈가 있었지만 '지금' 터진 특수한 이유 (시의성)",
    "key_positions": ["찬성/지지 측 핵심 주장", "반대/비판 측 핵심 주장"]
  }}
]
규칙:
- 반드시 JSON 배열만 출력 (설명 금지)
- 배열 길이 = {n}개 (입력 트렌드 수와 동일)
- publishable: 이 키워드로 의미 있는 SNS 콘텐츠를 만들 수 있으면 true. 문장 조각·의미불명이면 false
- corrected_keyword: 오타·축약어(예: "카이로류"→"아카이로 류")면 교정 원본 제시. 정상이면 빈 문자열
- safety_flag=true: 재난/사망/폭력/혐오/자살 및 정치·사회 갈등(반미/반일/반한/페미니즘) 트렌드
- relevance_score: 1~10, X에서 논의하기 적합할수록 높음
- joongyeon_kick: 0~100, 현상의 역설·이면·반전을 뽑을 수 있으면 높음. 단순 사실 전달이면 낮음
- trigger_event/chain_reaction/why_now: 컨텍스트에서 근거를 찾아 구체적으로 작성. 모르면 빈 문자열
- key_positions: 실제 논쟁이 있는 경우만 작성. 논쟁 없으면 빈 배열"""

_JSON_POLICY = LLMPolicy(response_mode="json", task_kind="json_extraction")


from analysis.scoring import (  # noqa: F401
    _compute_cross_source_confidence,
    _compute_freshness_score,
    _compute_signal_score,
)


async def _score_trend_async(
    keyword: str,
    context: MultiSourceContext,
    volume: str,
    volume_numeric: int,
    client: LLMClient,
    conn: sqlite3.Connection | None = None,
) -> ScoredTrend:
    """단일 트렌드 비동기 스코어링 (캐시 조회 → LLM 호출, 최대 2회 시도)."""
    # ── 캐시 조회: 카테고리 기반 차등 TTL (C1 최적화) ──
    if conn is not None:
        fingerprint = compute_fingerprint(keyword, volume_numeric)
        cached = await get_cached_score(conn, fingerprint, max_age_hours=18)
        if cached:
            log.info(f"  [캐시] '{keyword}' 스코어 재사용 ({cached['viral_potential']}점)")
            import json as _json
            angles = _json.loads(cached.get("suggested_angles", "[]")) if isinstance(
                cached.get("suggested_angles"), str) else cached.get("suggested_angles", [])
            return ScoredTrend(
                keyword=keyword,
                rank=0,
                volume_last_24h=volume_numeric,
                trend_acceleration=cached.get("trend_acceleration", "+0%"),
                viral_potential=cached["viral_potential"],
                top_insight=cached.get("top_insight", ""),
                suggested_angles=angles,
                best_hook_starter=cached.get("best_hook_starter", ""),
                context=context,
                sources=[TrendSource.GETDAYTRENDS],
            )

    # ── LLM 스코어링 (최대 2회 시도) ──
    from datetime import datetime as _dt
    safe_keyword = sanitize_keyword(keyword)
    prompt = SCORING_PROMPT_TEMPLATE.format(
        keyword=safe_keyword,
        volume=volume,
        context=context.to_combined_text(),
        current_time=_dt.now().strftime("%Y-%m-%d %H:%M (KST)"),
    )

    for attempt in range(2):
        try:
            response = await client.acreate(
                tier=TaskTier.LIGHTWEIGHT,
                max_tokens=1000,
                policy=_JSON_POLICY,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = _parse_json(response.text)

            if not parsed:
                log.warning(f"스코어링 JSON 파싱 실패 ({attempt + 1}/2): {keyword}")
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                return _default_scored_trend(keyword, context)

            raw_category = parsed.get("category", "")
            # "연예|스포츠|..." 형식 또는 파이프가 포함된 경우 첫 번째 값만 추출
            category = raw_category.split("|")[0].strip() if raw_category else ""

            # [v13.0] publishable 판정
            pub = parsed.get("publishable", True)
            if isinstance(pub, str):
                pub = pub.lower() not in ("false", "0", "no")

            return ScoredTrend(
                keyword=keyword,
                rank=0,
                volume_last_24h=parsed.get("volume_last_24h", 0),
                trend_acceleration=parsed.get("trend_acceleration", "+0%"),
                viral_potential=min(max(parsed.get("viral_potential", 0), 0), 100),
                top_insight=parsed.get("top_insight", ""),
                suggested_angles=parsed.get("suggested_angles", []),
                best_hook_starter=parsed.get("best_hook_starter", ""),
                category=category,
                context=context,
                sources=[TrendSource.GETDAYTRENDS],
                sentiment=parsed.get("sentiment", "neutral"),
                safety_flag=bool(parsed.get("safety_flag", False)),
                # [v8.0] 프롬프트 ① 필드
                why_trending=parsed.get("why_trending", ""),
                peak_status=parsed.get("peak_status", ""),
                relevance_score=min(max(int(parsed.get("relevance_score", 0)), 0), 10),
                # [v13.0] 게시 가능성 게이트
                publishable=bool(pub),
                publishability_reason=parsed.get("publishability_reason", ""),
                corrected_keyword=parsed.get("corrected_keyword", ""),
            )

        except Exception as e:
            log.error(f"스코어링 실패 ({attempt + 1}/2) ({keyword}): {e}")
            if attempt == 0:
                await asyncio.sleep(1)

    return _default_scored_trend(keyword, context)





# ══════════════════════════════════════════════════════
#  배치 스코어링 (Phase 2: 5개/LLM 호출, 비용 ~70% 절감)
# ══════════════════════════════════════════════════════

_BATCH_SIZE = 5  # 한 번에 스코어링할 트렌드 수


async def _batch_score_async(
    batch: list[tuple["RawTrend", "MultiSourceContext"]],
    client,
    conn,
    config: "AppConfig | None" = None,
    bucket: int = 5000,
) -> list["ScoredTrend"]:
    """
    트렌드 배치(최대 _BATCH_SIZE개)를 1회 LLM 호출로 스코어링.
    캐시 히트 항목은 LLM 호출에서 제외해 비용 절약.
    실패 시 각 항목을 개별 스코어링으로 폴백.
    """
    # ── 캐시 분리 ──
    need_llm: list[tuple["RawTrend", "MultiSourceContext"]] = []
    cached_results: dict[str, "ScoredTrend"] = {}

    if conn is not None:
        for trend, ctx in batch:
            fp = compute_fingerprint(trend.name, trend.volume_numeric, bucket)
            cached = await get_cached_score(conn, fp, max_age_hours=18)
            if cached:
                import json as _json
                angles = _json.loads(cached.get("suggested_angles", "[]")) \
                    if isinstance(cached.get("suggested_angles"), str) \
                    else cached.get("suggested_angles", [])
                log.info(f"  [캐시] '{trend.name}' 스코어 재사용 ({cached['viral_potential']}점)")
                cached_results[trend.name] = ScoredTrend(
                    keyword=trend.name, rank=0,
                    volume_last_24h=trend.volume_numeric,
                    trend_acceleration=cached.get("trend_acceleration", "+0%"),
                    viral_potential=cached["viral_potential"],
                    top_insight=cached.get("top_insight", ""),
                    suggested_angles=angles,
                    best_hook_starter=cached.get("best_hook_starter", ""),
                    context=ctx, sources=[TrendSource.GETDAYTRENDS],
                    sentiment=cached.get("sentiment", "neutral"),
                    safety_flag=bool(cached.get("safety_flag", 0)),
                    cross_source_confidence=_compute_cross_source_confidence(
                        trend.volume_numeric, ctx
                    ),
                )
            else:
                need_llm.append((trend, ctx))
    else:
        need_llm = list(batch)

    results: list["ScoredTrend"] = []

    if need_llm:
        # ── 배치 LLM 호출 ──
        from datetime import datetime as _dt
        current_time = _dt.now().strftime("%Y-%m-%d %H:%M (KST)")
        trends_json = json.dumps(
            [{"keyword": t.name, "volume": t.volume, "context": ctx.to_combined_text()}
             for t, ctx in need_llm],
            ensure_ascii=False,
        )
        prompt = BATCH_SCORING_PROMPT_TEMPLATE.format(
            n=len(need_llm),
            trends_json=trends_json,
            current_time=current_time,
        )
        # [Phase 1] Instructor 우선 시도 → 실패 시 기존 JSON 파싱 폴백
        parsed_list: list[dict] | None = await _score_batch_instructor(
            prompt, len(need_llm)
        )

        if parsed_list is None:
            # 기존 경로: shared/llm 클라이언트 + 수동 JSON 파싱
            for attempt in range(2):
                try:
                    response = await client.acreate(
                        tier=TaskTier.LIGHTWEIGHT,
                        max_tokens=600 * len(need_llm),
                        policy=_JSON_POLICY,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    text = response.text.strip()
                    if text.startswith("{"):
                        text = text[1:].lstrip()
                    parsed_list = _parse_json_array(text)
                    if parsed_list and len(parsed_list) == len(need_llm):
                        break
                    log.warning(f"배치 스코어링 응답 길이 불일치: {len(parsed_list) if parsed_list else 0} vs {len(need_llm)}")
                    parsed_list = None
                except Exception as e:
                    log.error(f"배치 스코어링 실패 ({attempt + 1}/2): {e}")
                    if attempt == 0:
                        await asyncio.sleep(1)

        if parsed_list:
            for (trend, ctx), item in zip(need_llm, parsed_list):
                keyword = sanitize_keyword(trend.name)
                # [v9.0 B-1] DB에서 실제 velocity 조회
                vel = 0.0
                if conn is not None:
                    try:
                        from db import get_volume_velocity
                        vel = await get_volume_velocity(conn, keyword)
                    except Exception:
                        pass
                results.append(_parse_scored_trend_from_dict(
                    item, keyword, trend.volume_numeric, ctx, config, velocity=vel
                ))
        else:
            # 배치 실패 → 개별 스코어링 폴백
            log.warning(f"배치 스코어링 실패 → 개별 폴백 ({len(need_llm)}개)")
            fallback = await asyncio.gather(
                *[_score_trend_async(t.name, ctx, t.volume, t.volume_numeric, client, conn)
                  for t, ctx in need_llm],
                return_exceptions=True,
            )
            for (trend, ctx), res in zip(need_llm, fallback):
                if isinstance(res, Exception):
                    results.append(_default_scored_trend(trend.name, ctx))
                else:
                    results.append(res)

    # ── 원래 순서대로 병합 ──
    ordered: list["ScoredTrend"] = []
    for trend, ctx in batch:
        if trend.name in cached_results:
            ordered.append(cached_results[trend.name])
        else:
            match = next((r for r in results if r.keyword == sanitize_keyword(trend.name)), None)
            ordered.append(match if match else _default_scored_trend(trend.name, ctx))
    return ordered

# ══════════════════════════════════════════════════════
#  Async Orchestrator
# ══════════════════════════════════════════════════════

async def _analyze_trends_async(
    raw_trends: list[RawTrend],
    contexts: dict[str, MultiSourceContext],
    config: AppConfig,
    conn: sqlite3.Connection | None = None,
) -> list[ScoredTrend]:
    """
    전체 트렌드 비동기 배치 스코어링.
    v3.0: _BATCH_SIZE(5)개씨 묶어 LLM 호출 → 비용 ~70% 절감.
    v4.0: Phase3 히스토리 패턴 보정 + Phase4 중연 킥 기반 장문 조건 연동.
    """
    client = get_client()

    # [v9.0] 로컬 클러스터링 (Jaccard + Embedding)
    # [v14.0] Gemini Embedding 2 기반 의미적 유사도 추가
    clusters = []
    if config.enable_clustering:
        threshold = getattr(config, "jaccard_cluster_threshold", 0.35)
        use_emb = getattr(config, "enable_embedding_clustering", True)
        emb_threshold = getattr(config, "embedding_cluster_threshold", 0.75)
        raw_trends, contexts, clusters = cluster_trends_local(
            raw_trends, contexts, threshold,
            use_embedding=use_emb,
            embedding_threshold=emb_threshold,
        )

    # [v14.1] 클러스터 정보를 컨텍스트에 주입 (스코어링 정확도 향상)
    if clusters:
        cluster_map: dict[str, list[str]] = {}
        for c in clusters:
            if len(c.members) > 1:
                cluster_map[c.representative] = [m for m in c.members if m != c.representative]
        for rep, related in cluster_map.items():
            ctx = contexts.get(rep, MultiSourceContext())
            related_str = ", ".join(related[:5])
            cluster_hint = f"\n[관련 트렌드 (의미적 클러스터)]: {related_str} → 이 주제가 여러 검색어로 확산 중"
            # news_insight에 클러스터 힌트 추가
            if ctx.news_insight:
                ctx = MultiSourceContext(
                    twitter_insight=ctx.twitter_insight,
                    reddit_insight=ctx.reddit_insight,
                    news_insight=ctx.news_insight + cluster_hint,
                )
            else:
                ctx = MultiSourceContext(
                    twitter_insight=ctx.twitter_insight,
                    reddit_insight=ctx.reddit_insight,
                    news_insight=cluster_hint,
                )
            contexts[rep] = ctx
        log.info(f"[클러스터 힌트] {len(cluster_map)}개 대표 트렌드에 관련 키워드 정보 주입")

    # [v14.1] 임베딩 기반 카테고리 사전 분류 힌트
    try:
        from shared.embeddings import embed_texts, cosine_similarity as _cos_sim

        _CATEGORY_REFS = {
            "정치": "국회 대통령 정당 선거 법안 정책",
            "경제": "주가 환율 금리 GDP 실적 무역",
            "테크": "AI 반도체 스마트폰 앱 서비스 소프트웨어",
            "사회": "교육 범죄 사고 환경 복지 인구",
            "스포츠": "축구 야구 농구 올림픽 경기 감독",
            "연예": "드라마 영화 아이돌 가수 배우 컴백",
            "국제": "외교 전쟁 유엔 미국 중국 정상회담",
        }
        ref_texts = list(_CATEGORY_REFS.values())
        ref_keys = list(_CATEGORY_REFS.keys())
        ref_vectors = embed_texts(ref_texts, task_type="SEMANTIC_SIMILARITY")

        if ref_vectors:
            trend_names = [t.name for t in raw_trends]
            trend_vectors = embed_texts(trend_names, task_type="SEMANTIC_SIMILARITY")
            if trend_vectors:
                for i, t in enumerate(raw_trends):
                    scores = {cat: _cos_sim(trend_vectors[i], ref_vectors[j])
                              for j, cat in enumerate(ref_keys)}
                    best_cat = max(scores, key=scores.get)
                    best_score = scores[best_cat]
                    if best_score >= 0.50:  # 최소 신뢰도
                        ctx = contexts.get(t.name, MultiSourceContext())
                        cat_hint = f"\n[카테고리 힌트 (임베딩)]: {best_cat} (신뢰도: {best_score:.2f})"
                        contexts[t.name] = MultiSourceContext(
                            twitter_insight=ctx.twitter_insight,
                            reddit_insight=ctx.reddit_insight,
                            news_insight=(ctx.news_insight or "") + cat_hint,
                        )
                log.info(f"[카테고리 사전분류] {len(raw_trends)}개 트렌드에 임베딩 기반 카테고리 힌트 주입")
    except Exception as _e:
        log.debug(f"[카테고리 사전분류] 사용 불가 (무시): {_e}")

    # 배치 분할 (5개씩)
    pairs = [(t, contexts.get(t.name, MultiSourceContext())) for t in raw_trends]
    batches = [pairs[i:i + _BATCH_SIZE] for i in range(0, len(pairs), _BATCH_SIZE)]
    bucket = getattr(config, "cache_volume_bucket", 5000)

    log.info(f"  배치 스코어링 시작: {len(raw_trends)}개 → {len(batches)}배치 (배치크기={_BATCH_SIZE})")
    batch_results = await asyncio.gather(
        *[_batch_score_async(b, client, conn, config, bucket) for b in batches],
        return_exceptions=True,
    )

    scored: list[ScoredTrend] = []
    for batch, raw_batch in zip(batch_results, batches):
        if isinstance(batch, Exception):
            log.error(f"배치 스코어링 전체 예외: {batch}")
            for trend, ctx in raw_batch:
                scored.append(_default_scored_trend(trend.name, ctx))
            continue
        scored.extend(batch)

    # 소스 정보 보완 및 랜킹 재정렬
    for result in scored:
        trend_map = {t.name: t for t in raw_trends}
        trend = trend_map.get(result.keyword)
        if trend:
            result.rank = trend.volume_numeric
            result.country = trend.country or config.country

        context = result.context or MultiSourceContext()
        sources = [TrendSource.GETDAYTRENDS]
        if context.twitter_insight and "미설정" not in context.twitter_insight:
            sources.append(TrendSource.TWITTER)
        if context.reddit_insight and "없음" not in context.reddit_insight:
            sources.append(TrendSource.REDDIT)
        if context.news_insight and "없음" not in context.news_insight:
            sources.append(TrendSource.GOOGLE_NEWS)
        result.sources = sources

    # Phase 3: 히스토리 패턴 보정 [v9.0] N+1 → 배치 조회
    if config.enable_history_correction and conn is not None:
        _HISTORY_MULTIPLIER = {
            "new":     1.10,
            "rising":  1.15,
            "stable":  0.90,
            "falling": 0.75,
        }
        try:
            from db import get_trend_history_patterns_batch
            pattern_map = await get_trend_history_patterns_batch(
                conn, [r.keyword for r in scored], days=7
            )
        except Exception as _e:
            log.debug(f"배치 히스토리 조회 실패 (무시): {_e}")
            pattern_map = {}

        for result in scored:
            pattern = pattern_map.get(result.keyword, {"score_trend": "new", "is_recurring": False, "seen_count": 0})
            score_trend = pattern.get("score_trend", "new")
            mult = _HISTORY_MULTIPLIER.get(score_trend, 1.0)
            if pattern.get("is_recurring") and pattern.get("seen_count", 0) >= 5:
                mult *= 0.8
                log.debug(f"  [Phase3 반복 패널티] '{result.keyword}' ×0.8 (5회 이상 등장)")
            if mult != 1.0:
                before = result.viral_potential
                result.viral_potential = min(int(result.viral_potential * mult), 100)
                log.debug(
                    f"  [Phase3 히스토리] '{result.keyword}' [{score_trend}] "
                    f"×{mult:.2f} → {before}점 → {result.viral_potential}점"
                )

    # Phase 4: 중연 킥 기반 장문 조건 연동
    kick_threshold = getattr(config, "joongyeon_kick_long_form_threshold", 75)
    for result in scored:
        if result.joongyeon_kick >= kick_threshold and \
                result.viral_potential < config.long_form_min_score:
            result.viral_potential = config.long_form_min_score
            log.debug(
                f"  [Phase4 킥] '{result.keyword}' kick={result.joongyeon_kick} → 장문 미니스코어 우회"
            )

    # Phase 5: [v9.0 C-6] 이머징 트렌드 감지
    if getattr(config, 'enable_emerging_detection', True) and conn is not None:
        vel_threshold = getattr(config, 'emerging_velocity_threshold', 2.0)
        vol_cap = getattr(config, 'emerging_volume_cap', 5000)
        try:
            from db import get_volume_velocity
            for result in scored:
                vel = await get_volume_velocity(conn, result.keyword)
                result.velocity = vel
                if vel >= vel_threshold and result.volume_last_24h < vol_cap:
                    result.is_emerging = True
                    bonus = 30
                    before = result.viral_potential
                    result.viral_potential = min(result.viral_potential + bonus, 100)
                    log.info(
                        f"  [Phase5 이머징] '{result.keyword}' "
                        f"velocity={vel:.1f}x, vol={result.volume_last_24h} "
                        f"→ +{bonus}점 ({before}→{result.viral_potential})"
                    )
        except Exception as _e:
            log.debug(f"이머징 감지 실패 (무시): {_e}")

    scored.sort(key=lambda x: x.viral_potential, reverse=True)
    for i, s in enumerate(scored):
        s.rank = i + 1

    safety_count = sum(1 for s in scored if s.safety_flag)
    confidence_low = sum(1 for s in scored if s.cross_source_confidence < 2)
    log.info(
        f"스코어링 완료: {len(scored)}개 "
        f"(최고 점수: {scored[0].viral_potential if scored else 0}, "
        f"safety_flag: {safety_count}건, "
        f"저신뢰 트렌드: {confidence_low}건)"
    )
    return scored


def analyze_trends(
    raw_trends: list[RawTrend],
    contexts: dict[str, MultiSourceContext],
    config: AppConfig,
    conn: sqlite3.Connection | None = None,
) -> list[ScoredTrend]:
    """동기 래퍼. 내부적으로 비동기 병렬 스코어링 실행."""
    return run_async(_analyze_trends_async(raw_trends, contexts, config, conn))

