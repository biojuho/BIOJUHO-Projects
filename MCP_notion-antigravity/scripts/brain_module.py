import os
import json
import anthropic
from dotenv import load_dotenv

# 환경 변수 로드
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
load_dotenv(os.path.join(parent_dir, ".env"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

class BrainModule:
    def __init__(self):
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not found in .env")
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def analyze_news(self, category: str, articles: list, time_window: str = "") -> dict:
        """
        뉴스 리스트를 받아 요약, 인사이트, X 포스트를 생성합니다.
        articles: list of {'title': str, 'description': str, 'link': str}
        time_window: str (e.g., "2026-02-06 18:00 ~ 2026-02-07 07:00")
        """
        if not articles:
            return None

        # 프롬프트 구성
        news_text = ""
        for idx, art in enumerate(articles, 1):
            desc = art.get('description', '')[:200] if art.get('description') else ''
            news_text += f"{idx}. {art['title']}\n   - {desc}...\n\n"

        prompt = f"""당신은 X(트위터)에서 기술 뉴스를 전문적으로 다루는 콘텐츠 크리에이터 "Raphael"입니다.
Premium+ 사용자처럼 글자 제한 없이 자유롭게 긴 포스트를 작성할 수 있다고 가정하고, 하나의 긴 글(또는 자연스럽게 연결된 스레드) 형식으로 매우 가독성 높고 몰입감 있는 Tech 뉴스 요약을 작성해주세요.

[분석 대상 기간]: {time_window}
[뉴스 데이터]:
{news_text}

[작성 지침]
1. **언어**: 반드시 모든 내용을 **한국어(Korean)**로 작성하세요.
2. **길이**: **800~1200자 내외**로 정보를 압축하여 임팩트 있게 작성.
3. **도입부**: "오늘 Tech 핫 이슈: [키워드1, 2, 3]. 변화의 시작입니다." 같은 강렬한 한 줄 요약.
4. **본문 구성**: 핵심 뉴스(3~4개)별로 명확한 소제목(이모지 1개 + 짧은 제목) 사용.
    - 구조: **핵심 사실(1문장)** -> 배경/디테일(1-2문장 압축) -> 전망/의미(1문장).
    - 문단 사이 1줄 공백 유지.
5. **톤앤매너**: 캐주얼하고 신뢰감 있는 전문가 톤 ("충격적이에요", "기대돼요").
6. **금지**: 해시태그(#) 절대 사용 금지.
7. **마무리**: 독자 참여 유도 1문장 ("가장 충격적인 소식은 무엇인가요? 댓글로!").

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
            message = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2500,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # JSON 파싱
            text = message.content[0].text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.replace("```", "")
            
            # Remove potential leading/trailing whitespace again
            text = text.strip()

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # Fallback: Try to fix unescaped newlines in the JSON string
                # This is a naive fix but often works for LLM output
                import re
                print("[Brain Warning] Parsing failed, attempting auto-fix (unescaped chars & trailing commas)...")
                
                # 1. Fix trailing commas before } or ]
                text = re.sub(r',(\s*[}\]])', r'\1', text)
                
                # 2. Try strict=False (though python json is strict by default on control chars)
                try:
                    return json.loads(text, strict=False)
                except json.JSONDecodeError:
                    pass

                # 3. Final attempt: Escape unescaped newlines within string values
                # This is hard to do perfectly with regex without a parser, but basic attempt:
                # (Skipping complex logic to avoid breaking valid JSON, relying on 1 & 2 for now)
                
                # Retry parsing after trailing comma fix
                try:
                    return json.loads(text)
                except:
                    pass

                return None

        except Exception as e:
            print(f"[Brain Error] {e}")
            # print(f"[Debug Raw Text] {text[:500]}...") # Uncomment for debug
            return None

if __name__ == "__main__":
    # Test Code
    print("Brain Module Test (Claude)...")
    brain = BrainModule()
    test_data = [
        {"title": "Bitcoin surges past $100k", "description": "Crypto market is booming as institutional investors flock in."},
        {"title": "Ethereum upgrade successful", "description": "Gas fees lowered significantly after the new patch."}
    ]
    result = brain.analyze_news("Crypto", test_data)
    if result:
        print("Summary:", result.get("summary"))
        print("Insight:", result.get("insight"))
        print("X Post:", result.get("x_post"))
    else:
        print("Failed to analyze news.")
