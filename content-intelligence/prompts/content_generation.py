"""3단계 — 콘텐츠 생성 프롬프트 템플릿."""

CONTENT_GENERATION_SYSTEM = """\
너는 멀티플랫폼 콘텐츠 크리에이터야.
각 플랫폼의 특성, 톤앤매너, 알고리즘 우대 요소를 정확히 반영한 콘텐츠를 제작해.
AI가 쓴 느낌이 나지 않도록, 자연스럽고 생동감 있는 문체를 유지해.

금지 사항:
- "~에 대해 알아보겠습니다" 같은 블로그체 도입부
- "이상으로 ~에 대해 알아보았습니다" 같은 마무리
- "충격적인", "획기적인", "game-changing" 같은 빈 과장 수식어
- "오늘은 ~를 소개합니다" 같은 뻔한 시작"""


def build_content_prompt(
    platform: str,
    project_name: str,
    core_message: str,
    target_audience: str,
    trend_summary: str,
    regulation_checklist: str,
) -> str:
    """플랫폼별 콘텐츠 생성 프롬프트를 생성한다."""

    platform_guides = {
        "x": _x_guide(),
        "threads": _threads_guide(),
        "naver": _naver_guide(),
    }

    guide = platform_guides.get(platform, f"■ {platform} 콘텐츠\n- 일반 포스트 형태로 작성")

    return f"""\
[컨텍스트 입력]
- 프로젝트명: {project_name}
- 프로젝트 핵심 메시지: {core_message}
- 타겟 오디언스: {target_audience}
- 이번 주 트렌드 요약:
{trend_summary}
- 플랫폼 규제 체크리스트:
{regulation_checklist}

[작업]
위 컨텍스트를 바탕으로 아래 기준에 맞는 콘텐츠를 제작해줘.

{guide}

■ 출력 형식 — 반드시 아래 JSON 구조로 응답해줘:
```json
{{
  "platform": "{platform}",
  "contents": [
    {{
      "content_type": "post 또는 thread 또는 blog",
      "title": "제목 (블로그만 해당, 나머지는 빈 문자열)",
      "body": "본문 내용",
      "hashtags": ["#해시태그1"],
      "trend_keywords_used": ["사용된_트렌드키워드"],
      "self_check": {{
        "trend_reflected": true,
        "regulation_compliant": true,
        "algorithm_optimized": true,
        "warnings": []
      }}
    }}
  ]
}}
```

반드시 JSON만 응답하고, 다른 텍스트는 포함하지 마."""


def _x_guide() -> str:
    return """\
■ X 게시물 (3종 생성)
1. 단문 포스트 (280자 이내)
   - 트렌드 키워드를 자연스럽게 녹여서 반영
   - 해시태그 0~2개 (무분별한 해시태그는 알고리즘 패널티)
   - 마지막 문장은 반드시 킥(Kick): 펀치라인·반전·날카로운 질문
   - 인용 RT를 유도할 수 있는 관점 제시

2. 장문 포스트 (X Premium+, 1000~2000자)
   - 첫 3줄 안에 후킹 + 핵심 주장 (스크롤 패스 방지)
   - 소제목/번호 달지 말고, 한 흐름의 분석 글로 작성
   - 데이터 포인트는 볼드로 강조
   - 진심 어린 관점 → "그래서 뭐?" 질문에 답하는 구조

3. 쓰레드 (2연결)
   - Post 1 (Hook Post, ~2500자): 호기심 유발 → 데이터 제시 → 분석
   - Post 2 (Kick Post, ~800자): "그래서 뭐?" 답변 → 공유 유도 킥"""


def _threads_guide() -> str:
    return """\
■ Threads 게시물 (2종 생성)
1. 공감형 포스트
   - "나" 시점으로 작성, 친구에게 이야기하듯 캐주얼한 톤
   - "솔직히", "근데 진짜", "나만 이런 거 아니지?" 같은 MZ 구어체
   - 트렌드 키워드를 일상적 맥락에 자연스럽게 연결
   - 마지막에 이항 질문으로 참여 유도 ("A vs B, 너는?")

2. 인사이트형 포스트
   - 짧은 관찰 + 본인만의 해석
   - 외부 링크 최소화 (Threads 알고리즘 패널티 회피)
   - 공감 + 놀라움을 동시에 주는 관점
   - 이모지 적절히 사용 (과하지 않게, 2~3개)"""


def _naver_guide() -> str:
    return """\
■ 네이버 블로그 포스트 (1종 생성)
- 제목: 검색 키워드를 자연스럽게 포함 (30~50자)
- 본문 구조:
  1. 도입 (상황 공감 or 질문으로 시작, 3~4문장)
  2. 본론 (소제목 2~3개로 구분, 각 300~500자)
  3. 결론 (핵심 요약 + 다음 글 예고 or CTA)
- SEO 최적화:
  - 본문 키워드 밀도 2~3% 유지
  - LSI(잠재 의미 인덱싱) 키워드 자연 배치
  - 소제목(##)에 핵심 키워드 포함
- C-Rank 친화:
  - 전문성 있는 정보형 콘텐츠 (1500자 이상)
  - 카테고리 일관성 유지
  - 원본 이미지 삽입 위치 표시: [이미지: 설명]
- D.I.A. 최적화:
  - 체류 시간 확보를 위한 단락 구분
  - 목차/요약 박스 포함
  - 외부 링크 최소화 (저품질 판정 회피)
- seo_keywords 필드에 3~5개 핵심 키워드를 리스트로 제공"""
