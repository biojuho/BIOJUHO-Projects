"""
=======================================================
  X(Twitter) 트렌드 자동 트윗 생성기
  - 2시간마다 한국 실시간 트렌드 수집
  - Claude AI로 5종 트윗 시안 생성
  - Notion 또는 Google Sheets에 자동 저장
=======================================================
"""

import os
import time
import json
import logging
import schedule
import requests
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup

import anthropic

# 저장 방식별 임포트
try:
    from notion_client import Client as NotionClient
    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    COLOR = True
except ImportError:
    COLOR = False

# ── 로깅 설정 ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("tweet_bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ── 환경변수 로드 ───────────────────────────────────────
load_dotenv()

ANTHROPIC_API_KEY       = os.getenv("ANTHROPIC_API_KEY", "")
NOTION_TOKEN            = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID      = os.getenv("NOTION_DATABASE_ID", "")
GOOGLE_SERVICE_JSON     = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials.json")
GOOGLE_SHEET_ID         = os.getenv("GOOGLE_SHEET_ID", "")
STORAGE_TYPE            = os.getenv("STORAGE_TYPE", "notion").lower()
SCHEDULE_MINUTES        = int(os.getenv("SCHEDULE_INTERVAL_MINUTES", "120"))
TONE                    = os.getenv("TONE", "친근하고 위트 있는 동네 친구")


# ══════════════════════════════════════════════════════
#  1. 트렌드 수집 모듈
# ══════════════════════════════════════════════════════

def fetch_trending_topics(max_topics: int = 5) -> list[dict]:
    """
    getdaytrends.com에서 한국 X 실시간 트렌드 TOP N을 수집합니다.
    Returns: [{"rank": 1, "topic": "봄동비빔밥"}, ...]
    """
    url = "https://getdaytrends.com/korea/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        trends = []
        # 테이블 행에서 트렌드 텍스트 추출
        rows = soup.select("table tr")
        for row in rows:
            link = row.select_one("a")
            if link:
                topic = link.get_text(strip=True)
                # 해시태그 기호 정리
                topic = topic.lstrip("#").strip()
                if topic:
                    trends.append(topic)
            if len(trends) >= max_topics:
                break

        if not trends:
            log.warning("트렌드를 파싱하지 못했습니다. 대체 트렌드를 사용합니다.")
            return _fallback_trends()

        result = [{"rank": i + 1, "topic": t} for i, t in enumerate(trends)]
        log.info(f"✅ 트렌드 수집 완료: {[r['topic'] for r in result]}")
        return result

    except Exception as e:
        log.error(f"트렌드 수집 실패: {e} → 대체 트렌드 사용")
        return _fallback_trends()


def _fallback_trends() -> list[dict]:
    """스크래핑 실패 시 사용하는 일반적인 대체 주제들"""
    fallbacks = ["주말 계획", "점심 메뉴", "날씨", "커피", "퇴근"]
    return [{"rank": i + 1, "topic": t} for i, t in enumerate(fallbacks)]


# ══════════════════════════════════════════════════════
#  2. Claude AI 트윗 생성 모듈
# ══════════════════════════════════════════════════════

SYSTEM_PROMPT = """
당신은 X(트위터) 트렌드에 민감하며, 팔로워들과의 티키타카(소통)에 능한
'소셜 커뮤니티 매니저 겸 카피라이터'입니다.

팔로워들이 무의식적으로 답글을 달고 싶게 만드는, 280자 이내의 임팩트 있는 트윗을 작성합니다.

[작성 가이드라인]
1. 공감과 논쟁: 누구나 공감할 수 있는 일상적 이야기나 가벼운 찬반 주제
2. 트렌드 결합: 밈(Meme)이나 X 특유의 텍스트 포맷 활용
3. 질문형 구조: 문장 끝을 질문으로 맺어 독자가 자신의 이야기를 꺼내도록 유도
4. 각 트윗은 반드시 280자 이내

[출력 형식 - 반드시 JSON으로만 응답]
{
  "topic": "주제명",
  "tweets": [
    {"type": "공감 유도형", "content": "트윗 내용"},
    {"type": "가벼운 꿀팁형", "content": "트윗 내용"},
    {"type": "찬반 질문형", "content": "트윗 내용"},
    {"type": "동기부여/명언형", "content": "트윗 내용"},
    {"type": "유머/밈 활용형", "content": "트윗 내용"}
  ]
}
"""


def generate_tweets(topic: str, tone: str = TONE) -> dict | None:
    """
    Claude API를 호출해 주어진 트렌드 주제로 5종 트윗 시안을 생성합니다.
    Returns: {"topic": ..., "tweets": [...]}
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    user_message = f"""
오늘 다룰 주제/상황: {topic}
화자의 톤앤매너: {tone}

위 주제로 5가지 유형의 트윗 시안을 JSON 형식으로만 작성해주세요.
반드시 JSON만 출력하고 다른 설명은 일절 없어야 합니다.
"""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )
        raw = response.content[0].text.strip()

        # JSON 파싱 (마크다운 코드블록 제거)
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)

        log.info(f"✅ 트윗 생성 완료: 주제 '{topic}'")
        return data

    except json.JSONDecodeError as e:
        log.error(f"JSON 파싱 실패 (주제: {topic}): {e}\n원문: {raw[:200]}")
        return None
    except Exception as e:
        log.error(f"Claude API 호출 실패: {e}")
        return None


# ══════════════════════════════════════════════════════
#  3. Notion 저장 모듈
# ══════════════════════════════════════════════════════

def save_to_notion(tweets_data: dict, trend_rank: int) -> bool:
    """
    생성된 트윗을 Notion 데이터베이스에 저장합니다.
    
    필요한 Notion DB 속성:
    - 제목 (title)
    - 주제 (rich_text)
    - 순위 (number)
    - 생성시각 (date)
    - 공감유도형 (rich_text)
    - 꿀팁형 (rich_text)
    - 찬반질문형 (rich_text)
    - 명언형 (rich_text)
    - 유머밈형 (rich_text)
    - 상태 (select): 대기중 / 게시완료
    """
    if not NOTION_AVAILABLE:
        log.error("notion-client 패키지가 설치되지 않았습니다: pip install notion-client")
        return False

    notion = NotionClient(auth=NOTION_TOKEN)
    now = datetime.now()
    topic = tweets_data.get("topic", "Unknown")
    tweets = tweets_data.get("tweets", [])

    # 트윗 유형별로 딕셔너리 구성
    tweet_map = {t["type"]: t["content"] for t in tweets}

    title = f"[트렌드 #{trend_rank}] {topic} — {now.strftime('%Y-%m-%d %H:%M')}"

    properties = {
        "제목": {
            "title": [{"text": {"content": title}}]
        },
        "주제": {
            "rich_text": [{"text": {"content": topic}}]
        },
        "순위": {
            "number": trend_rank
        },
        "생성시각": {
            "date": {"start": now.isoformat()}
        },
        "공감유도형": {
            "rich_text": [{"text": {"content": tweet_map.get("공감 유도형", "")}}]
        },
        "꿀팁형": {
            "rich_text": [{"text": {"content": tweet_map.get("가벼운 꿀팁형", "")}}]
        },
        "찬반질문형": {
            "rich_text": [{"text": {"content": tweet_map.get("찬반 질문형", "")}}]
        },
        "명언형": {
            "rich_text": [{"text": {"content": tweet_map.get("동기부여/명언형", "")}}]
        },
        "유머밈형": {
            "rich_text": [{"text": {"content": tweet_map.get("유머/밈 활용형", "")}}]
        },
        "상태": {
            "select": {"name": "대기중"}
        }
    }

    try:
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=properties
        )
        log.info(f"✅ Notion 저장 완료: '{title}'")
        return True
    except Exception as e:
        log.error(f"Notion 저장 실패: {e}")
        return False


# ══════════════════════════════════════════════════════
#  4. Google Sheets 저장 모듈
# ══════════════════════════════════════════════════════

def save_to_google_sheets(tweets_data: dict, trend_rank: int) -> bool:
    """
    생성된 트윗을 Google Sheets에 저장합니다.
    """
    if not GSPREAD_AVAILABLE:
        log.error("gspread 패키지가 설치되지 않았습니다: pip install gspread google-auth")
        return False

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(GOOGLE_SERVICE_JSON, scopes=scopes)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(GOOGLE_SHEET_ID).sheet1

        # 헤더가 없으면 첫 행에 헤더 추가
        existing = sheet.get_all_values()
        if not existing:
            headers = [
                "생성시각", "순위", "주제",
                "공감유도형", "꿀팁형", "찬반질문형", "명언형", "유머밈형", "상태"
            ]
            sheet.append_row(headers, value_input_option="USER_ENTERED")

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        topic = tweets_data.get("topic", "Unknown")
        tweets = tweets_data.get("tweets", [])
        tweet_map = {t["type"]: t["content"] for t in tweets}

        row = [
            now,
            trend_rank,
            topic,
            tweet_map.get("공감 유도형", ""),
            tweet_map.get("가벼운 꿀팁형", ""),
            tweet_map.get("찬반 질문형", ""),
            tweet_map.get("동기부여/명언형", ""),
            tweet_map.get("유머/밈 활용형", ""),
            "대기중"
        ]
        sheet.append_row(row, value_input_option="USER_ENTERED")

        log.info(f"✅ Google Sheets 저장 완료: 주제 '{topic}'")
        return True

    except FileNotFoundError:
        log.error(f"서비스 계정 JSON 파일을 찾을 수 없습니다: {GOOGLE_SERVICE_JSON}")
        return False
    except Exception as e:
        log.error(f"Google Sheets 저장 실패: {e}")
        return False


# ══════════════════════════════════════════════════════
#  5. 저장 라우터 (Notion / Google Sheets 분기)
# ══════════════════════════════════════════════════════

def save_tweets(tweets_data: dict, trend_rank: int) -> bool:
    if STORAGE_TYPE == "notion":
        return save_to_notion(tweets_data, trend_rank)
    elif STORAGE_TYPE == "google_sheets":
        return save_to_google_sheets(tweets_data, trend_rank)
    else:
        log.error(f"알 수 없는 STORAGE_TYPE: '{STORAGE_TYPE}'. 'notion' 또는 'google_sheets'를 사용하세요.")
        return False


# ══════════════════════════════════════════════════════
#  6. 메인 작업 함수 (2시간마다 실행)
# ══════════════════════════════════════════════════════

def print_banner():
    banner = """
╔═══════════════════════════════════════════════════╗
║     X 트렌드 자동 트윗 생성기 v1.0               ║
║     Claude AI × Getdaytrends × Auto Save          ║
╚═══════════════════════════════════════════════════╝
"""
    print(banner)


def run_job():
    """
    전체 파이프라인 실행:
    1. 트렌드 수집 → 2. 트윗 생성 → 3. 저장
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 55
    print(f"\n{separator}")
    print(f"  🚀 작업 시작: {now_str}")
    print(separator)

    # Step 1: 트렌드 수집
    print("\n📡 [1/3] 실시간 트렌드 수집 중...")
    trends = fetch_trending_topics(max_topics=3)  # 상위 3개 주제 처리

    success_count = 0

    for trend in trends:
        rank  = trend["rank"]
        topic = trend["topic"]

        print(f"\n🔥 트렌드 #{rank}: [{topic}]")

        # Step 2: 트윗 생성
        print(f"   ✍️  [2/3] Claude AI 트윗 생성 중...")
        tweets_data = generate_tweets(topic)
        if not tweets_data:
            print(f"   ❌ 생성 실패, 다음 트렌드로 넘어갑니다.")
            continue

        # 콘솔 미리보기
        _print_tweet_preview(tweets_data)

        # Step 3: 저장
        print(f"   💾 [3/3] {STORAGE_TYPE.upper()}에 저장 중...")
        ok = save_tweets(tweets_data, rank)
        if ok:
            success_count += 1
        
        # API rate limit 방지용 짧은 대기
        time.sleep(3)

    print(f"\n{separator}")
    print(f"  ✅ 완료: {success_count}/{len(trends)}개 저장 성공")
    print(f"  ⏰ 다음 실행: {SCHEDULE_MINUTES}분 후")
    print(separator)


def _print_tweet_preview(tweets_data: dict):
    """콘솔에 트윗 시안 미리보기 출력"""
    topic = tweets_data.get("topic", "")
    tweets = tweets_data.get("tweets", [])
    print(f"\n   ── 트윗 미리보기: [{topic}] ──")
    for t in tweets:
        label   = t.get("type", "")
        content = t.get("content", "")
        # 길면 줄여서 표시
        preview = content[:60] + "..." if len(content) > 60 else content
        print(f"   [{label}] {preview}")


# ══════════════════════════════════════════════════════
#  7. 설정 유효성 검사
# ══════════════════════════════════════════════════════

def validate_config() -> bool:
    errors = []

    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your_anthropic_api_key_here":
        errors.append("❌ ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    if STORAGE_TYPE == "notion":
        if not NOTION_TOKEN or NOTION_TOKEN == "your_notion_integration_token_here":
            errors.append("❌ NOTION_TOKEN이 설정되지 않았습니다.")
        if not NOTION_DATABASE_ID or NOTION_DATABASE_ID == "your_notion_database_id_here":
            errors.append("❌ NOTION_DATABASE_ID가 설정되지 않았습니다.")
        if not NOTION_AVAILABLE:
            errors.append("❌ notion-client 패키지가 없습니다: pip install notion-client")

    elif STORAGE_TYPE == "google_sheets":
        if not GOOGLE_SHEET_ID or GOOGLE_SHEET_ID == "your_google_sheet_id_here":
            errors.append("❌ GOOGLE_SHEET_ID가 설정되지 않았습니다.")
        if not os.path.exists(GOOGLE_SERVICE_JSON):
            errors.append(f"❌ Google 서비스 계정 JSON이 없습니다: {GOOGLE_SERVICE_JSON}")
        if not GSPREAD_AVAILABLE:
            errors.append("❌ gspread 패키지가 없습니다: pip install gspread google-auth")

    if errors:
        print("\n⚠️  설정 오류가 있습니다:")
        for e in errors:
            print(f"  {e}")
        print("\n  → .env 파일을 확인해주세요 (.env.example 참고)\n")
        return False

    print(f"""
✅ 설정 확인 완료
   저장 방식    : {STORAGE_TYPE.upper()}
   실행 간격    : {SCHEDULE_MINUTES}분 (= {SCHEDULE_MINUTES // 60}시간)
   톤앤매너     : {TONE}
""")
    return True


# ══════════════════════════════════════════════════════
#  8. 진입점
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    print_banner()

    # 설정 검사
    if not validate_config():
        exit(1)

    # 즉시 1회 실행
    print("⚡ 첫 번째 실행을 즉시 시작합니다...\n")
    run_job()

    # 스케줄 등록 (N분마다 반복)
    schedule.every(SCHEDULE_MINUTES).minutes.do(run_job)

    print(f"\n⏱️  스케줄러 가동 중... ({SCHEDULE_MINUTES}분마다 자동 실행)")
    print("   중단하려면 Ctrl+C 를 누르세요.\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # 30초마다 스케줄 체크
    except KeyboardInterrupt:
        print("\n\n👋 스케줄러를 종료합니다. 수고하셨습니다!")
