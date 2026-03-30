# 📈 X(Twitter) 리치 데이터 수집 가이드

V11 프롬프트를 통해 생성된 트윗/블로그 쓰레드의 성과를 측정하기 위한 가이드입니다. 자동화 여건(API 등급)에 따라 수동 수집과 자동화 방식 중 선택하여 도입합니다.

---

## 방법 1. 수동 수집 (초기 권장)

X(Twitter) Free API 등급에서는 트윗의 Impressions(노출) / Engagements(참여)를 조회하는 Analytics 엔드포인트 접근이 제한됩니다. 따라서 매주 성과 리뷰 시 정량 데이터를 수동으로 추출하는 것을 권장합니다.

1. **X Analytics 접속:** [analytics.twitter.com](https://analytics.twitter.com)에 로그인.
2. **트윗 활동 탭 이동:** 상단 메뉴에서 '트윗(Tweets)' 선택.
3. **데이터 추출:**
   - 우측 상단 '기간(Date Range)'을 지난 1주일 단위로 설정.
   - '데이터 내보내기(Export Data)' 버튼을 눌러 CSV 다운로드.
4. **리뷰 템플릿 연동:**
   - 엑셀/구글 스프레드시트에서 "노출수(Impressions)"를 기준으로 내림차순 정렬하여 Top 3 / Worst 포스트 식별.
   - 데이터값을 `docs/templates/weekly_content_review.md` (Notion 페이지)에 복사해 회고 진행.

---

## 방법 2. 자동화 방식 (추후 Pro/Basic 티어 업그레이드 시)

트위터 API가 Basic/Pro 티어 이상이 되거나 `tweepy` 모듈과 확장 엔드포인트를 지원하는 환경이 마련되면 Python 자동화 데몬을 구성할 수 있습니다.

### API 수집 예시 스크립트 (초안)

```python
# scripts/fetch_twitter_metrics.py
import os
import tweepy
import json
from datetime import datetime, timedelta

def get_weekly_metrics():
    # API 키 로드 (기존 GetDayTrends 방식)
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")

    # Tweepy Client 초기화
    client = tweepy.Client(bearer_token=bearer_token)
    user_id = client.get_me().data.id

    # 최근 일주일 작성 트윗 추출
    start_time = datetime.utcnow() - timedelta(days=7)

    # tweet_fields에 유기적 지표(organic_metrics), 비공개 지표(non_public_metrics) 지정 필요 (권한 주의)
    tweets = client.get_users_tweets(
        id=user_id,
        start_time=start_time,
        max_results=100,
        tweet_fields=['public_metrics', 'organic_metrics']
    )

    if not tweets.data:
        return "조회된 트윗 없음"

    report = []
    for tweet in tweets.data:
        metrics = tweet.organic_metrics if hasattr(tweet, 'organic_metrics') else tweet.public_metrics
        report.append({
            "id": tweet.id,
            "text": tweet.text[:50] + "...",
            "impressions": metrics.get('impression_count', 0),
            "engagements": metrics.get('like_count', 0) + metrics.get('retweet_count', 0)
        })

    return sorted(report, key=lambda x: x['impressions'], reverse=True)

if __name__ == "__main__":
    report = get_weekly_metrics()
    with open("scripts/metrics_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
```

### 파이프라인 연계 방안
위 스크립트가 활성화되면 `cost_dashboard.py`와 유사하게 **매주 일요일 저녁** 실행되도록 Task Scheduler에 등록하여 주간 리뷰에 참조할 `metrics_report.json` 파일을 정기 생성하도록 구성합니다.
