"""
getdaytrends v9.0 - 로컬 Jaccard 클러스터링 테스트 (A-3)
cluster_trends_local 함수의 유사도 기반 트렌드 병합 검증.
"""

from analyzer import _jaccard_similarity, cluster_trends_local
from models import MultiSourceContext, RawTrend, TrendSource

# ══════════════════════════════════════════════════════
#  Jaccard 유사도 단위 테스트
# ══════════════════════════════════════════════════════


def test_jaccard_identical():
    """동일 문자열 → 유사도 1.0."""
    assert _jaccard_similarity("삼성전자 주가", "삼성전자 주가") == 1.0


def test_jaccard_no_overlap():
    """겹치는 토큰 없음 → 유사도 0.0."""
    assert _jaccard_similarity("삼성전자 주가", "날씨 예보") == 0.0


def test_jaccard_partial_overlap():
    """부분 겹침 → 0 < 유사도 < 1."""
    sim = _jaccard_similarity("삼성전자 주가 상승", "삼성전자 주가 하락")
    assert 0.0 < sim < 1.0
    # '삼성전자', '주가' 겹침 (2), 전체 합집합 ('삼성전자','주가','상승','하락') = 4 → 0.5
    assert sim == 0.5


def test_jaccard_ignores_short_tokens():
    """2자 미만 토큰은 유사도 계산에서 제외."""
    sim = _jaccard_similarity("A B 삼성전자", "C D 삼성전자")
    # 'A', 'B', 'C', 'D'는 2자 미만이므로 제외, '삼성전자'만 남음 → 1.0
    assert sim == 1.0


def test_jaccard_empty_string():
    """빈 문자열 → 유사도 0.0."""
    assert _jaccard_similarity("", "삼성전자") == 0.0
    assert _jaccard_similarity("삼성전자", "") == 0.0
    assert _jaccard_similarity("", "") == 0.0


def test_jaccard_case_insensitive():
    """대소문자 무시 비교."""
    sim = _jaccard_similarity("OpenAI GPT", "openai gpt")
    assert sim == 1.0


# ══════════════════════════════════════════════════════
#  cluster_trends_local 통합 테스트
# ══════════════════════════════════════════════════════


def _make_raw(name: str, volume: int = 1000) -> RawTrend:
    return RawTrend(
        name=name,
        source=TrendSource.GETDAYTRENDS,
        volume=f"{volume:,}",
        volume_numeric=volume,
    )


def _make_ctx(twitter: str = "", news: str = "") -> MultiSourceContext:
    return MultiSourceContext(twitter_insight=twitter, news_insight=news)


def test_cluster_identical_keywords():
    """정확히 같은 토큰 구성의 트렌드는 하나로 병합."""
    trends = [
        _make_raw("삼성전자 주가 상승", 5000),
        _make_raw("삼성전자 주가 하락", 3000),  # Jaccard = 0.5 >= 0.35
        _make_raw("날씨 예보 서울", 2000),  # 다른 주제 (병합 안 됨)
    ]
    contexts = {
        "삼성전자 주가 상승": _make_ctx(twitter="상승 관련 트윗"),
        "삼성전자 주가 하락": _make_ctx(twitter="하락 관련 트윗"),
        "날씨 예보 서울": _make_ctx(),
    }
    reps, merged_ctx, clusters = cluster_trends_local(trends, contexts)

    assert len(reps) == 2  # 삼성전자 병합(1) + 날씨(1)
    rep_names = {r.name for r in reps}
    assert "삼성전자 주가 상승" in rep_names  # 볼륨 높은 쪽이 대표
    assert "날씨 예보 서울" in rep_names


def test_cluster_preserves_standalone():
    """유사하지 않은 키워드는 각각 독립 클러스터로 유지."""
    trends = [
        _make_raw("삼성전자 주가", 5000),
        _make_raw("날씨 예보 서울", 3000),
    ]
    contexts = {
        "삼성전자 주가": _make_ctx(),
        "날씨 예보 서울": _make_ctx(),
    }
    reps, _, clusters = cluster_trends_local(trends, contexts)

    assert len(reps) == 2
    assert len(clusters) == 2
    for c in clusters:
        assert len(c.members) == 1


def test_cluster_two_or_fewer_passthrough():
    """2개 이하 트렌드는 클러스터링 없이 그대로 통과."""
    trends = [_make_raw("테스트")]
    contexts = {"테스트": _make_ctx()}
    reps, _, clusters = cluster_trends_local(trends, contexts)

    assert len(reps) == 1
    assert len(clusters) == 1
    assert clusters[0].representative == "테스트"


def test_cluster_context_merge():
    """병합된 클러스터의 컨텍스트가 올바르게 합쳐지는지 확인."""
    trends = [
        _make_raw("OpenAI GPT 신기능", 8000),
        _make_raw("OpenAI GPT 업데이트", 4000),  # Jaccard ≥ 0.35
        _make_raw("날씨 예보 주말", 1000),  # 병합 안 되는 다른 주제
    ]
    contexts = {
        "OpenAI GPT 신기능": _make_ctx(twitter="신기능 트윗", news="신기능 뉴스"),
        "OpenAI GPT 업데이트": _make_ctx(twitter="업데이트 트윗", news="업데이트 뉴스"),
        "날씨 예보 주말": _make_ctx(),
    }
    reps, merged_ctx, clusters = cluster_trends_local(trends, contexts)

    assert len(reps) == 2  # OpenAI 병합(1) + 날씨(1)
    # OpenAI 대표의 컨텍스트가 병합되었는지 확인
    openai_rep = next((r for r in reps if "OpenAI" in r.name), None)
    assert openai_rep is not None
    rep_ctx = merged_ctx[openai_rep.name]
    assert "신기능 트윗" in rep_ctx.twitter_insight
    assert "업데이트 트윗" in rep_ctx.twitter_insight
    assert "신기능 뉴스" in rep_ctx.news_insight
    assert "업데이트 뉴스" in rep_ctx.news_insight


def test_cluster_volume_representative():
    """대표 키워드는 볼륨이 가장 높은 트렌드로 선택."""
    trends = [
        _make_raw("테크 트렌드 뉴스", 1000),
        _make_raw("테크 트렌드 분석", 9000),
        _make_raw("테크 트렌드 요약", 5000),
        _make_raw("날씨 예보 주말", 500),  # 병합 안 되는 다른 주제
    ]
    contexts = {t.name: _make_ctx() for t in trends}
    reps, _, clusters = cluster_trends_local(trends, contexts)

    # 테크 트렌드 3개는 병합되고, 날씨는 독립
    assert len(reps) == 2
    rep_names = {r.name for r in reps}
    assert "테크 트렌드 분석" in rep_names  # 볼륨 9000으로 최고
    assert "날씨 예보 주말" in rep_names


def test_cluster_custom_threshold():
    """높은 임계값으로 클러스터링하면 병합이 줄어듦 (Jaccard 전용)."""
    trends = [
        _make_raw("삼성전자 주가 상승", 5000),
        _make_raw("삼성전자 주가 하락", 3000),  # Jaccard = 0.5
        _make_raw("날씨 예보 내일", 2000),  # 다른 주제
    ]
    contexts = {t.name: _make_ctx() for t in trends}

    # threshold=0.6 → Jaccard 0.5 < 0.6이므로 병합 안 됨 → 3개 모두 독립
    reps, _, clusters = cluster_trends_local(trends, contexts, threshold=0.6, use_embedding=False)
    assert len(reps) == 3

    # threshold=0.4 → Jaccard 0.5 >= 0.4이므로 삼성전자 2개 병합 → 2개
    reps2, _, clusters2 = cluster_trends_local(trends, contexts, threshold=0.4, use_embedding=False)
    assert len(reps2) == 2


# ══════════════════════════════════════════════════════
#  [v14.0] 임베딩 클러스터링 관련 테스트
# ══════════════════════════════════════════════════════


def test_cluster_embedding_fallback_to_jaccard():
    """임베딩 비활성화 시 Jaccard로 폴백되는지 확인."""
    trends = [
        _make_raw("삼성전자 주가 상승", 5000),
        _make_raw("삼성전자 주가 하락", 3000),
        _make_raw("날씨 예보 서울", 2000),
    ]
    contexts = {t.name: _make_ctx() for t in trends}

    # use_embedding=False → Jaccard만 사용
    reps, _, clusters = cluster_trends_local(trends, contexts, threshold=0.35, use_embedding=False)
    assert len(reps) == 2  # Jaccard=0.5 >= 0.35 → 삼성전자 병합
    rep_names = {r.name for r in reps}
    assert "삼성전자 주가 상승" in rep_names


def test_cluster_with_embedding_disabled_preserves_standalone():
    """임베딩 비활성화 + 서로 다른 키워드 → 독립 유지."""
    trends = [
        _make_raw("AI 자율주행", 3000),
        _make_raw("비트코인 가격", 2000),
        _make_raw("날씨 예보 주말", 1000),
    ]
    contexts = {t.name: _make_ctx() for t in trends}

    reps, _, clusters = cluster_trends_local(trends, contexts, use_embedding=False)
    assert len(reps) == 3
    assert len(clusters) == 3
