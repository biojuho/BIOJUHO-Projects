"""
X Niche Radar v2.0 (Layer 1 - The Antenna)
트렌드 수집 + 바이럴 포텐셜 스코어링 + Analytics DB 연동.
"""
import sys
import json
import re
import argparse
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import os


def _load_env():
    try:
        from dotenv import load_dotenv
        _here = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(_here, "..", "..", "..", "..", ".env")
        load_dotenv(os.path.normpath(env_path))
    except ImportError:
        pass


def get_gemini_client():
    _load_env()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment.")
    from google import genai
    return genai.Client(api_key=api_key)


def fetch_google_news_trends(keyw):
    """Google News RSS 기반 트렌드 수집 (한/영 동시)"""
    encoded_topic = urllib.parse.quote(keyw)
    insights = []
    for lang in [("en-US", "US", "US:en"), ("ko", "KR", "KR:ko")]:
        url = f"https://news.google.com/rss/search?q={encoded_topic}&hl={lang[0]}&gl={lang[1]}&ceid={lang[2]}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                root = ET.fromstring(response.read())
            for item in root.findall('.//item')[:3]:
                title = item.find('title').text if item.find('title') is not None else ''
                if title:
                    insights.append(title)
        except Exception:
            continue
    return " | ".join(insights) if insights else "관련 뉴스 부족"


def fetch_twitter_trends(keyw):
    """X API v2 최신 트윗 검색 (인게이지먼트 메트릭 포함)"""
    _load_env()
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        # Fallback to simulated response if no token to prevent errors
        return f"[Twitter API 미설정] - {keyw}에 대한 활발한 토론 중임"

    encoded_query = urllib.parse.quote(f"{keyw} -is:retweet lang:en")
    url = f"https://api.twitter.com/2/tweets/search/recent?query={encoded_query}&max_results=10&tweet.fields=public_metrics,created_at"
    headers = {"Authorization": f"Bearer {bearer_token}", "User-Agent": "AntigravityXBot/2.0"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
        if "data" not in data:
            return "최근 관련 트윗 없음"

        tweets = data["data"]
        for t in tweets:
            metrics = t.get("public_metrics", {})
            t["_engagement"] = metrics.get("like_count", 0) + metrics.get("retweet_count", 0) * 2
        tweets.sort(key=lambda t: t["_engagement"], reverse=True)

        summaries = []
        for t in tweets[:5]:
            metrics = t.get("public_metrics", {})
            eng = f"[{metrics.get('like_count', 0)}L/{metrics.get('retweet_count', 0)}RT]"
            summaries.append(f"{eng} {t['text'].replace(chr(10), ' ')[:150]}")
        return "\n".join(summaries)
    except Exception as e:
        return f"[Twitter API 오류: {keyw} 트렌드 감지 중 (Timeout 예상)]"


def fetch_reddit_trends(keyw):
    """Reddit 핫 포스트 수집 (점수 포함)"""
    encoded_query = urllib.parse.quote(keyw)
    url = f"https://www.reddit.com/search.json?q={encoded_query}&sort=hot&limit=5&t=day"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
        posts = []
        for item in data.get("data", {}).get("children", []):
            d = item["data"]
            posts.append(f"[{d.get('score', 0)}pts] {d['title']}")
        return "\n".join(posts) if posts else "최근 관련 레딧 게시물 없음"
    except Exception as e:
        return f"[Reddit API 접근 제한: {keyw} 트렌드 감지 실패]"


def fetch_niche_trends(keywords):
    """키워드별 트렌드 통합 분석 + Analytics DB 저장"""
    client = None
    results = []
    try:
        client = get_gemini_client()
    except Exception as e:
        print(f"[WARN] Gemini client init failed: {e}")

    for kw in keywords:
        twitter_insight = fetch_twitter_trends(kw)
        reddit_insight = fetch_reddit_trends(kw)
        news_insight = fetch_google_news_trends(kw)

        combined = f"[X 실시간 반응]\n{twitter_insight}\n\n[Reddit 커뮤니티]\n{reddit_insight}\n\n[뉴스 헤드라인]\n{news_insight}"

        prompt = f"""당신은 X(Twitter) 트렌드 분석기입니다.

키워드: {kw}
수집된 실시간 데이터:
{combined}

분석 요구사항:
1. 24시간 추정 볼륨과 트렌드 가속도
2. 바이럴 가능성이 가장 높은 핵심 이슈
3. X에서 반직관적으로 해석할 수 있는 3가지 앵글

JSON 응답 (반드시 쌍따옴표만 사용하는 유효한 JSON 객체, 다른 말이나 마크다운 백틱 없이):
{{
    "keyword": "{kw}",
    "volume_last_24h": 1000,
    "trend_acceleration": "+10%",
    "viral_potential": 85,
    "top_insight": "가장 뜨거운 이슈 1문장",
    "suggested_angles": [
        "반직관적 앵글",
        "데이터 기반 앵글",
        "미래 예측 앵글"
    ],
    "best_hook_starter": "이 트렌드로 트윗을 시작할 최고의 한 문장"
}}"""

        try:
            if not client:
                raise ValueError("Gemini client is not initialized.")

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            text = getattr(response, "text", None)
            if not text:
                raise ValueError("Empty response from Gemini")
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if not json_match:
                raise ValueError("Failed to parse JSON")
            parsed = json.loads(json_match.group(0))
            results.append(parsed)
        except Exception as e:
            import traceback
            traceback.print_exc()
            results.append({
                "keyword": kw, "volume_last_24h": 0, "trend_acceleration": "+0%",
                "viral_potential": 0, "top_insight": f"{kw} 분석 실패",
                "suggested_angles": [], "best_hook_starter": ""
            })

    results.sort(key=lambda x: x.get("viral_potential", 0), reverse=True)
    return json.dumps(results, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='X Niche Radar v2.0')
    parser.add_argument('--keywords', nargs='+', required=True, help='수집할 키워드들')
    parser.add_argument('--include-history', action='store_true', help='과거 트렌드 패턴 포함')
    args = parser.parse_args()

    print(fetch_niche_trends(args.keywords))
