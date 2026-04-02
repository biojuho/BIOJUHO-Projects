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
    personas: list[dict] | None = None,
) -> str:
    """플랫폼별 콘텐츠 생성 프롬프트를 생성한다."""

    platform_guides = {
        "x": _x_guide(),
        "x_thread": _x_thread_guide(),
        "threads": _threads_guide(),
        "naver": _naver_guide(),
    }

    guide = platform_guides.get(platform, f"■ {platform} 콘텐츠\n- 일반 포스트 형태로 작성")
    persona_block = _build_persona_block(platform, personas)

    return f"""\
[컨텍스트 입력]
- 프로젝트명: {project_name}
- 프로젝트 핵심 메시지: {core_message}
- 타겟 오디언스: {target_audience}
- 이번 주 트렌드 요약:
{trend_summary}
- 플랫폼 규제 체크리스트:
{regulation_checklist}
{persona_block}
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


def _build_persona_block(platform: str, personas: list[dict] | None) -> str:
    """플랫폼 친화적인 페르소나를 선택해 독자 심리 컨텍스트 블록을 생성한다."""
    if not personas:
        return ""

    # 플랫폼 친화도 기준으로 가장 적합한 페르소나 선택
    matched = [p for p in personas if platform in p.get("platform_affinity", [])]
    if not matched:
        matched = personas

    # 다수 페르소나 중 pain_points가 가장 많은 것 우선, 동점 시 id 오름차순 (안정 선택)
    persona = max(matched, key=lambda p: (len(p.get("pain_points", [])), p.get("id", "")))

    pain = "\n".join(f"    · {pt}" for pt in persona.get("pain_points", [])[:3])
    hooks = " / ".join(f'"{h}"' for h in persona.get("preferred_hooks", [])[:2])
    triggers = " / ".join(f'"{t}"' for t in persona.get("share_triggers", [])[:2])

    return f"""
- 독자 페르소나 [{persona.get('name', '')}]: {persona.get('description', '')}
  페인포인트:
{pain}
  선호 Hook 패턴: {hooks}
  공유 유발 요인: {triggers}
"""


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


def _x_thread_guide() -> str:
    return """\
■ X 스레드 (5~7트윗 연결형, 고참여 포맷)

구조:
1. Hook 트윗 (1번, 280자 이내)
   - 스크롤을 멈추는 강렬한 첫 문장
   - "이걸 알고 나면 절대 돌아갈 수 없다" 류의 호기심 유발
   - 숫자/통계가 있으면 더 강력
   - 마지막에 "🧵" 또는 "스레드 ↓" 표시

2. Body 트윗 (2~5번, 각 280자 이내)
   - 각 트윗은 독립적으로도 의미가 있어야 함
   - 하나의 논점 = 하나의 트윗
   - 트윗 간 자연스러운 연결 ("그런데", "더 놀라운 건", "핵심은")
   - 데이터/사례/인용은 별도 트윗으로 분리
   - 중간에 공감 트윗 1개 삽입 ("나도 처음엔 이게 진짜인가 싶었다")

3. Kick 트윗 (마지막, 280자 이내)
   - 전체를 관통하는 핵심 인사이트 1줄
   - RT/북마크 유도: "저장해두고 나중에 다시 보세요"
   - 또는 행동 유도: "지금 바로 해볼 수 있는 것은..."

규칙:
- 해시태그는 마지막 트윗에만 1~2개
- 각 트윗 280자 엄수 (한국어 기준)
- 이모지는 트윗당 최대 1개

■ 출력 JSON의 thread_posts 필드에 배열로:
```json
"thread_posts": [
  {"index": 0, "role": "hook", "body": "첫 트윗 내용"},
  {"index": 1, "role": "body", "body": "두 번째 트윗"},
  ...
  {"index": N, "role": "kick", "body": "마지막 트윗"}
]
```
body 필드에는 전체 스레드를 \\n---\\n 로 연결한 전문을 넣어줘."""


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

[검색 의도 분류 — 아래 4가지 중 트렌드에 가장 적합한 유형 1가지를 선택해 구조화]
A. 정보성 (알고 싶다): "AI 에이전트란 무엇인가 — 2026 개념 정리"
B. 비교형 (고르고 싶다): "ChatGPT vs Claude vs Gemini — 실무자 기준 비교"
C. How-to (하고 싶다): "Claude API 연동 5단계 — 실제 코드 포함"
D. 후기형 (믿고 싶다): "AI 자동화 도입 3개월 후 실제로 달라진 것들"

[2026 네이버 제목 패턴 — 검색 CTR 최적화]
- 숫자 + 핵심어 + 감성어: "AI 자동화 5가지 — 안 쓰면 손해인 이유"
- 의문형 + 정보 예고: "왜 전문가들은 LLM 프롬프트를 이렇게 짤까?"
- 비교/대조형: "ChatGPT로 안 됐던 것, Claude로 해결한 방법"
- 결과 중심형: "AI 글쓰기 도구 바꾸고 하루 3시간 아낀 방법"
- 제목 길이 30~45자 (모바일 검색 노출 기준)

[본문 구조]
  1. 도입 (공감 상황 or 문제 제기, 3~4문장) — 독자가 "나 얘기네" 느끼게
  2. 목차 박스 (소제목 2~3개 미리 보여주기, 체류시간 확보)
  3. 본론 (소제목 ## 포함, 각 300~500자, 핵심 키워드 자연 삽입)
  4. 결론 (핵심 1줄 요약 + 다음 글 예고 or 댓글 CTA)

[SEO 최적화]
  - 본문 키워드 밀도 2~3% 유지
  - LSI(잠재 의미 인덱싱) 키워드 자연 배치
  - 소제목(##)에 핵심 키워드 포함
  - 내부 링크 가이드: "[관련 글: ___에 대한 자세한 내용은 아래 글을 참고하세요]" 형태로 1~2곳 안내

[C-Rank / D.I.A. 최적화]
  - 전문성 있는 정보형 콘텐츠 (1500자 이상)
  - 원본 이미지 삽입 위치 표시: [이미지: 설명]
  - 체류 시간 확보를 위한 단락 구분
  - 외부 링크 최소화 (저품질 판정 회피)

- seo_keywords 필드에 3~5개 핵심 키워드를 리스트로 제공
- search_intent 필드에 선택한 유형 코드 (A/B/C/D) 제공"""
