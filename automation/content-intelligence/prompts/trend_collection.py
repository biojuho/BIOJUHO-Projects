"""1단계 — 트렌드 수집 프롬프트 템플릿."""

TREND_COLLECTION_SYSTEM = """\
너는 소셜 미디어 트렌드 분석가야.
주어진 플랫폼에서 현재 급상승 중인 트렌드를 정확하게 분석하고 구조화된 데이터로 정리해.
과장하지 말고, 데이터에 기반한 분석만 제공해."""


def build_trend_prompt(
    platform: str,
    project_fields: list[str],
    top_n: int = 5,
) -> str:
    """플랫폼별 트렌드 수집 프롬프트를 생성한다."""
    fields_str = ", ".join(project_fields) if project_fields else "(일반)"

    platform_specifics = {
        "x": (
            "X (구 Twitter)",
            "- 실시간 트렌딩 키워드 및 해시태그\n"
            "- 인용 RT가 많은 바이럴 콘텐츠 포맷\n"
            "- Premium+ 장문 트렌드 여부",
        ),
        "threads": (
            "Threads (Meta)",
            "- Threads 추천 피드에서 반응이 높은 키워드/주제\n"
            "- 대화형·캐주얼 톤의 바이럴 포맷\n"
            "- 이미지/캐러셀 vs 텍스트 비중",
        ),
        "naver": (
            "네이버 블로그",
            "- 네이버 DataLab 급상승 검색어\n"
            "- 블로그 인기글의 포맷 (리스트형, 후기형, 정보형)\n"
            "- C-Rank 상위 노출 키워드 경향",
        ),
    }

    name, specifics = platform_specifics.get(
        platform, (platform, "- 해당 플랫폼의 주요 트렌드")
    )

    return f"""\
[작업]
아래 플랫폼의 현재 주요 트렌드를 조사해서 정리해줘.

■ 조사 대상: {name}

■ 플랫폼 특화 조사 항목
{specifics}

■ 각 트렌드별 정리 항목 (TOP {top_n})
1. 급상승 키워드/해시태그
2. 바이럴되고 있는 콘텐츠 포맷 (예: 캐러셀, 쓰레드형, 숏폼, 장문 등)
3. 사용자 반응이 높은 톤앤매너 경향 (유머, 진정성, 논쟁 유발, 교육적 등)
4. 우리 프로젝트 분야 [{fields_str}]와 연결 가능한 트렌드 접점

■ 출력 형식 — 반드시 아래 JSON 구조로 응답해줘:
```json
{{
  "platform": "{platform}",
  "trends": [
    {{
      "keyword": "키워드명",
      "hashtags": ["#해시태그1", "#해시태그2"],
      "volume": 추정검색량_숫자,
      "format_trend": "인기포맷",
      "tone_trend": "톤경향",
      "project_connection": "프로젝트접점설명"
    }}
  ],
  "key_insights": [
    "핵심 인사이트 1",
    "핵심 인사이트 2",
    "핵심 인사이트 3"
  ]
}}
```

반드시 JSON만 응답하고, 다른 텍스트는 포함하지 마."""
