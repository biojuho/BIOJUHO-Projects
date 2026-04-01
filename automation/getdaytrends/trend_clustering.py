"""
getdaytrends — Trend Clustering (v14.0)
Jaccard + Gemini Embedding 2 기반 하이브리드 의미적 클러스터링.
analyzer.py에서 분리됨.
"""

from loguru import logger as log

try:
    from .models import MultiSourceContext, RawTrend, TrendCluster
except ImportError:
    from models import MultiSourceContext, RawTrend, TrendCluster

# ══════════════════════════════════════════════════════
#  Similarity Helpers
# ══════════════════════════════════════════════════════


def _jaccard_similarity(a: str, b: str) -> float:
    """형태소 단위 자카드 유사도 (0.0~1.0). 2자 미만 토큰은 제외."""
    tokens_a = {t for t in a.lower().split() if len(t) >= 2}
    tokens_b = {t for t in b.lower().split() if len(t) >= 2}
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _compute_similarity_pairs_embedding(
    names: list[str],
    threshold: float,
) -> list[tuple[int, int]] | None:
    """
    [v14.0] Gemini Embedding 2로 의미적 유사도 계산 후 threshold 이상 쌍 반환.
    실패 시 None 반환 (Jaccard 폴백 트리거).
    """
    try:
        from embeddings import compute_similarity_matrix, embed_texts

        vectors = embed_texts(names)
        if vectors is None or len(vectors) != len(names):
            return None

        sim_matrix = compute_similarity_matrix(vectors)
        pairs = []
        n = len(names)
        for i in range(n):
            for j in range(i + 1, n):
                if sim_matrix[i][j] >= threshold:
                    pairs.append((i, j))
                    log.debug(f"  [임베딩 유사] '{names[i]}' ↔ '{names[j]}' " f"= {sim_matrix[i][j]:.3f} ≥ {threshold}")
        return pairs

    except Exception as e:
        log.warning(f"[임베딩 클러스터링 실패] {e} → Jaccard 폴백")
        return None


# ══════════════════════════════════════════════════════
#  Cluster Merge (공통 로직)
# ══════════════════════════════════════════════════════


def _merge_clusters(
    raw_trends: list["RawTrend"],
    contexts: dict[str, "MultiSourceContext"],
    groups: dict[int, list[int]],
    names: list[str],
    method: str = "jaccard",
) -> tuple[list["RawTrend"], dict[str, "MultiSourceContext"], list["TrendCluster"]]:
    """Union-Find 그룹 결과 → 대표 선정 + 컨텍스트 병합 (공통 로직)."""
    trend_map = {t.name: t for t in raw_trends}
    clusters: list[TrendCluster] = []
    representatives: list["RawTrend"] = []

    for idxs in groups.values():
        members = [names[i] for i in idxs]
        # 대표 = 볼륨 최대
        rep_name = max(members, key=lambda nm: trend_map[nm].volume_numeric)

        # 컨텍스트 병합
        merged_tw, merged_rd, merged_nw = [], [], []
        for nm in members:
            ctx = contexts.get(nm, MultiSourceContext())
            if ctx.twitter_insight and "오류" not in ctx.twitter_insight:
                merged_tw.append(ctx.twitter_insight)
            if ctx.reddit_insight and "없음" not in ctx.reddit_insight:
                merged_rd.append(ctx.reddit_insight)
            if ctx.news_insight and "없음" not in ctx.news_insight:
                merged_nw.append(ctx.news_insight)

        merged_ctx = MultiSourceContext(
            twitter_insight="\n".join(merged_tw) or contexts.get(rep_name, MultiSourceContext()).twitter_insight,
            reddit_insight="\n".join(merged_rd) or contexts.get(rep_name, MultiSourceContext()).reddit_insight,
            news_insight="\n".join(merged_nw) or contexts.get(rep_name, MultiSourceContext()).news_insight,
        )
        contexts[rep_name] = merged_ctx
        clusters.append(TrendCluster(representative=rep_name, members=members, merged_context=merged_ctx))
        representatives.append(trend_map[rep_name])

    merged_count = sum(len(c.members) - 1 for c in clusters if len(c.members) > 1)
    if merged_count:
        log.info(f"[{method} 클러스터링] {len(raw_trends)}개 → {len(representatives)}개 " f"(병합 {merged_count}개)")

    return representatives, contexts, clusters


# ══════════════════════════════════════════════════════
#  Local Hybrid Clustering (v14.0)
# ══════════════════════════════════════════════════════


def cluster_trends_local(
    raw_trends: list["RawTrend"],
    contexts: dict[str, "MultiSourceContext"],
    threshold: float = 0.35,
    use_embedding: bool = True,
    embedding_threshold: float = 0.75,
) -> tuple[list["RawTrend"], dict[str, "MultiSourceContext"], list["TrendCluster"]]:
    """
    [v14.0] 하이브리드 의미적 클러스터링.

    1차: Gemini Embedding 2 기반 의미적 유사도 (use_embedding=True)
         → "BTS 컴백" ↔ "방탄소년단 신곡" 같은 의미적 중복 감지 가능
    2차: 임베딩 실패 시 Jaccard 유사도 폴백 (기존 v9.0 방식)

    Args:
        raw_trends: 수집된 트렌드 목록
        contexts: 트렌드별 멀티소스 컨텍스트
        threshold: Jaccard 유사도 임계값 (기본 0.35)
        use_embedding: Gemini Embedding 사용 여부 (기본 True)
        embedding_threshold: 임베딩 코사인 유사도 임계값 (기본 0.75)
    """
    if len(raw_trends) <= 2:
        clusters = [TrendCluster(representative=t.name, members=[t.name]) for t in raw_trends]
        return raw_trends, contexts, clusters

    names = [t.name for t in raw_trends]
    n = len(names)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    # [v14.0] 1차: 임베딩 기반 의미적 유사도 시도
    used_embedding = False
    if use_embedding:
        embedding_pairs = _compute_similarity_pairs_embedding(names, embedding_threshold)
        if embedding_pairs is not None:
            for i, j in embedding_pairs:
                union(i, j)
            used_embedding = True
            log.info(
                f"[임베딩 클러스터링] {len(names)}개 키워드 → "
                f"{len(embedding_pairs)}쌍 유사 감지 (threshold={embedding_threshold})"
            )

    # 2차: 임베딩 실패 시 Jaccard 폴백
    if not used_embedding:
        for i in range(n):
            for j in range(i + 1, n):
                if _jaccard_similarity(names[i], names[j]) >= threshold:
                    union(i, j)

    # 클러스터 그룹핑
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    method = "임베딩" if used_embedding else "Jaccard"
    return _merge_clusters(raw_trends, contexts, groups, names, method)


# ══════════════════════════════════════════════════════
#  LLM-based Clustering (기존 방식)
# ══════════════════════════════════════════════════════

CLUSTERING_PROMPT = """다음 트렌드 키워드 목록에서 의미적으로 유사한 키워드를 그루핑해주세요.
각 그룹에서 가장 대표적인 키워드 하나를 representative로 선택하세요.
단독 키워드는 자기 자신만 members에 넣으세요.

키워드 목록:
{keywords}

다음 JSON 배열 스키마로 정확히 응답:
[
  {{"representative": "대표 키워드", "members": ["키워드1", "키워드2"]}},
  {{"representative": "단독 키워드", "members": ["단독 키워드"]}}
]"""


def _call_cluster_llm(client, raw_trends: list[RawTrend]) -> list | None:
    """[B] LLM 클러스터링 API 호출 + JSON 파싱."""
    import json

    from shared.llm import TaskTier
    from shared.llm.models import LLMPolicy

    _JSON_POLICY = LLMPolicy(response_mode="json", task_kind="json_extraction")
    keywords = [t.name for t in raw_trends]
    prompt = CLUSTERING_PROMPT.format(keywords="\n".join(f"- {k}" for k in keywords))
    try:
        response = client.create(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=1000,
            policy=_JSON_POLICY,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.text.strip()
        if text.startswith("{"):
            text = text[1:].lstrip()
        return json.loads(text) if text else None
    except Exception as e:
        log.warning(f"클러스터링 API 실패, 스킵: {e}")
        return None


def _merge_member_contexts(
    members: list[str],
    contexts: dict[str, MultiSourceContext],
    rep: str,
) -> MultiSourceContext:
    """[B] 클러스터 멤버 컨텍스트를 대표 키워드 기준으로 병합."""
    merged_twitter, merged_reddit, merged_news = [], [], []
    for m in members:
        ctx = contexts.get(m, MultiSourceContext())
        if ctx.twitter_insight and "오류" not in ctx.twitter_insight:
            merged_twitter.append(ctx.twitter_insight)
        if ctx.reddit_insight and "없음" not in ctx.reddit_insight:
            merged_reddit.append(ctx.reddit_insight)
        if ctx.news_insight and "없음" not in ctx.news_insight:
            merged_news.append(ctx.news_insight)
    fallback = contexts.get(rep, MultiSourceContext())
    return MultiSourceContext(
        twitter_insight="\n".join(merged_twitter) if merged_twitter else fallback.twitter_insight,
        reddit_insight="\n".join(merged_reddit) if merged_reddit else fallback.reddit_insight,
        news_insight="\n".join(merged_news) if merged_news else fallback.news_insight,
    )


def _build_clusters_from_parsed(
    parsed: list,
    raw_trends: list[RawTrend],
    contexts: dict[str, MultiSourceContext],
) -> tuple[list[RawTrend], dict[str, MultiSourceContext], list[TrendCluster]]:
    """[B] LLM 응답으로부터 클러스터 목록을 구성하고 미클러스터 항목을 단독 추가."""
    trend_map = {t.name: t for t in raw_trends}
    clusters_list: list[TrendCluster] = []
    representative_names: set[str] = set()

    for group in parsed:
        rep = group.get("representative", "")
        members = group.get("members", [rep])
        if rep not in trend_map:
            valid = [m for m in members if m in trend_map]
            rep = valid[0] if valid else ""
        if not rep:
            continue
        merged_ctx = _merge_member_contexts(members, contexts, rep)
        contexts[rep] = merged_ctx
        clusters_list.append(TrendCluster(representative=rep, members=members, merged_context=merged_ctx))
        representative_names.add(rep)

    filtered = [t for t in raw_trends if t.name in representative_names]
    clustered_all: set[str] = set()
    for c in clusters_list:
        clustered_all.update(c.members)
    for t in raw_trends:
        if t.name not in clustered_all:
            filtered.append(t)
            clusters_list.append(TrendCluster(representative=t.name, members=[t.name]))

    return filtered, contexts, clusters_list


def cluster_trends(
    raw_trends: list[RawTrend],
    contexts: dict[str, MultiSourceContext],
    client,
) -> tuple[list[RawTrend], dict[str, MultiSourceContext], list[TrendCluster]]:
    """트렌드 클러스터링: 유사 키워드 그루핑 후 대표만 남김."""
    if len(raw_trends) <= 2:
        clusters = [TrendCluster(representative=t.name, members=[t.name]) for t in raw_trends]
        return raw_trends, contexts, clusters

    parsed = _call_cluster_llm(client, raw_trends)
    if not parsed:
        clusters = [TrendCluster(representative=t.name, members=[t.name]) for t in raw_trends]
        return raw_trends, contexts, clusters

    filtered, contexts, clusters_list = _build_clusters_from_parsed(parsed, raw_trends, contexts)
    merged_count = sum(len(c.members) for c in clusters_list if len(c.members) > 1)
    if merged_count:
        log.info(f"클러스터링: {len(raw_trends)}개 → {len(filtered)}개 (병합 {merged_count}개 키워드)")
    return filtered, contexts, clusters_list
