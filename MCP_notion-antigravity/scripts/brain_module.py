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

    def analyze_news(self, category: str, articles: list) -> dict:
        """
        뉴스 리스트를 받아 요약, 인사이트, X 포스트를 생성합니다.
        articles: list of {'title': str, 'description': str, 'link': str}
        """
        if not articles:
            return None

        # 프롬프트 구성
        news_text = ""
        for idx, art in enumerate(articles, 1):
            desc = art.get('description', '')[:200] if art.get('description') else ''
            news_text += f"{idx}. {art['title']}\n   - {desc}...\n\n"

        prompt = f"""당신은 "라프(Raf)"라는 이름의 전문 뉴스 분석가입니다.
다음 {category} 관련 뉴스를 분석하고 구조화된 리포트를 작성하세요.

[뉴스 데이터]
{news_text}

[출력 형식]
반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.
{{
    "summary": ["핵심 포인트 1", "핵심 포인트 2", "핵심 포인트 3"],
    "insight": "이 뉴스들이 왜 중요한지, 시장/사회에 어떤 영향을 미치는지 1-2문장으로 설명",
    "x_post": "{category} 관련 트렌드를 요약한 X(트위터) 포스트. 이모지 포함, 전문적이면서도 흥미롭게, 250-400자, 해시태그 2-3개 포함"
}}"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
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
            
            return json.loads(text.strip())
        except Exception as e:
            print(f"[Brain Error] {e}")
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
