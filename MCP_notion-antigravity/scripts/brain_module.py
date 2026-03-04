import json
import re
import sys
from pathlib import Path

# shared.llm 모듈 경로 추가
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from shared.llm import TaskTier, get_client


class BrainModule:
    def __init__(self):
        self.client = get_client()

    def _robust_json_parse(self, text: str) -> dict:
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            text = text.strip()
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        try:
            # Fix trailing commas
            text = re.sub(r',(\s*[}\]])', r'\1', text)
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"[Brain Error] Failed to parse JSON: {text[:100]}...")
            return None

    def analyze_news(self, category: str, articles: list, time_window: str = "", niche_trends: list = None) -> dict:
        """
        뉴스 리스트를 받아 요약, 인사이트, X 포스트를 생성합니다.
        articles: list of {'title': str, 'description': str, 'link': str}
        niche_trends: list of dicts containing x_radar trending data (X, Reddit, News volumes/angles)
        time_window: str (e.g., "2026-02-06 18:00 ~ 2026-02-07 07:00")
        """
        if not articles:
            return None

        # 프롬프트 구성
        news_text = ""
        for idx, art in enumerate(articles, 1):
            desc = art.get('description', '')[:200] if art.get('description') else ''
            news_text += f"{idx}. {art['title']}\n   - {desc}...\n\n"

        # 틈새 트렌드 (X Radar) 구성
        trends_text = ""
        if niche_trends:
            trends_text = "🎯 [X Radar 실시간 반응 분석 (트위터/레딧 트렌드 반영)]\n"
            for t in niche_trends[:3]:  # 상위 3개 트렌드만 사용
                trends_text += f"- 키워드: {t.get('keyword')}\n"
                trends_text += f"  - 반응 인사이트: {t.get('top_insight')}\n"
                trends_text += f"  - 바이럴 포텐셜 점수: {t.get('viral_potential')}/100\n"
                trends_text += f"  - 추천 앵글: {', '.join(t.get('suggested_angles', []))}\n"

        prompt = f"""당신은 X(트위터)에서 기술/경제 뉴스를 전문적으로 다루는 콘텐츠 크리에이터 "Raphael"입니다.
Premium+ 사용자처럼 글자 제한 없이 자유롭게 긴 포스트를 작성할 수 있다고 가정하고, 하나의 긴 글(또는 자연스럽게 연결된 스레드) 형식으로 매우 가독성 높고 몰입감 있는 Tech 뉴스 요약을 작성해주세요.

[분석 대상 기간]: {time_window}

[뉴스 원문 데이터]:
{news_text}

{trends_text}

[작성 지침]
1. **언어**: 반드시 모든 내용을 **한국어(Korean)**로 작성하세요.
2. **길이**: **800~1200자 내외**로 정보를 압축하여 임팩트 있게 작성.
3. **도입부**: "오늘의 핫 이슈: [키워드]. 변화의 시작입니다." 같은 강렬한 한 줄 요약.
4. **본문 구성**: 핵심 뉴스(3~4개)별로 명확한 소제목(이모지 1개 + 짧은 제목) 사용.
    - 구조: **핵심 사실(1문장)** -> 배경/디테일(1-2문장 압축) -> 전망/의미(1문장).
    - 문단 사이 1줄 공백 유지.
5. **트렌드 통합**: 만약 [X Radar 실시간 반응 분석] 데이터가 존재한다면
    - 그 데이터를 적극 활용하여 "현재 글로벌 트위터/레딧의 반응"이나 "새로 떠오르는 앵글"을 반드시 스레드 본문이나 인사이트에 녹여내세요.
6. **톤앤매너**: 캐주얼하고 신뢰감 있는 전문가 톤 ("충격적이에요", "기대돼요").
7. **금지**: 해시태그(#) 절대 사용 금지.
8. **마무리**: 독자 참여 유도 1문장 ("여러분의 생각은 어떠신가요? 댓글로!").

[출력 형식]
반드시 아래 JSON 형식으로만 응답하세요.
**주의: JSON 값 내부의 줄바꿈은 반드시 \\n으로 이스케이프 처리해야 합니다.**
{{
    "summary": ["핵심 1", "핵심 2", "핵심 3"],
    "insights": [
        {{
            "date": "YYYY-MM-DD",
            "topic": "주제",
            "insight": "핵심 분석",
            "importance": "중요성"
        }}
    ],
    "x_thread": [
        "작성된 긴 포스트의 전체 내용을 이 리스트의 첫 번째 요소로 모두 넣으세요. (줄바꿈은 \\n으로 표기)"
    ]
}}"""

        try:
            response = self.client.create(
                tier=TaskTier.MEDIUM,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            # JSON 파싱
            text = response.text
            if not text:
                print("[Brain Error] Empty response from LLM")
                return None
            return self._robust_json_parse(text.strip())

        except Exception as e:
            print(f"[Brain Error] {e}")
            return None

if __name__ == "__main__":
    # Test Code
    print("Brain Module Test (Gemini)...")
    brain = BrainModule()
    test_data = [
        {"title": "Bitcoin surges past $100k", "description": "Crypto market is booming as institutional investors flock in."},
        {"title": "Ethereum upgrade successful", "description": "Gas fees lowered significantly after the new patch."}
    ]
    result = brain.analyze_news("Crypto", test_data)
    if result:
        print("Summary:", result.get("summary"))
        print("Insights:", result.get("insights"))
        print("X Thread:", result.get("x_thread"))
    else:
        print("Failed to analyze news.")
