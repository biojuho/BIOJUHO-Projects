# Instagram Automation — Meta Developer App 설정 가이드

## 1단계: Meta Developer 앱 생성

1. [Meta Developers](https://developers.facebook.com/) 접속
2. **My Apps** → **Create App** → **Business** 선택
3. 앱 이름: `instagram-automation` (또는 원하는 이름)
4. 앱 목적: **Instagram Business** 선택

## 2단계: 필수 권한 추가

**Products** → **Instagram Graph API** 추가 후 아래 권한 요청:

| 권한 | 용도 |
|------|------|
| `instagram_basic` | 계정 정보 조회 |
| `instagram_content_publish` | 콘텐츠 발행 |
| `instagram_manage_comments` | 댓글 관리 |
| `instagram_manage_insights` | 인사이트 조회 |
| `instagram_manage_messages` | DM 관리 |
| `pages_read_engagement` | 페이지 엔게이지먼트 |

## 3단계: 비즈니스 계정 연결

1. 개인 인스타그램 → **설정** → **계정** → **프로페셔널 계정으로 전환** → **비즈니스** 선택
2. Facebook 페이지 연결 (필수)
3. Meta Developer App에서 **Instagram Accounts** → 해당 비즈니스 계정 연결

## 4단계: 시스템 유저 토큰 발급

1. [Business Suite](https://business.facebook.com/settings/system-users) → **시스템 사용자** 생성
2. 역할: `Admin`
3. **토큰 생성** → 위 권한 모두 체크 → `META_SYSTEM_USER_TOKEN`으로 사용
4. 이 토큰은 **만료 없음** (System User Token)

## 5단계: .env 설정

```bash
# instagram-automation/.env
META_APP_ID=your_app_id_here
META_APP_SECRET=your_app_secret_here
META_SYSTEM_USER_TOKEN=your_system_user_token_here
META_IG_USER_ID=your_ig_business_account_id
META_PAGE_ID=your_facebook_page_id
META_API_VERSION=v21.0
WEBHOOK_VERIFY_TOKEN=my_custom_verify_token_here

# LLM (shared module uses these)
GOOGLE_API_KEY=your_google_api_key

# Notifications
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

## 6단계: App Review 제출

- 프로덕션 사용을 위해 Meta App Review 필요 (개발 모드에서는 자신의 계정만 접근 가능)
- 각 권한에 대해 사용 사례 설명 + 스크린캐스트 필요
- 보통 3-5 영업일 소요

## 주요 제약사항 (2025-2026)

| 항목 | 제한 |
|------|------|
| API 호출 | 200 calls/hour/user |
| 게시 제한 | 100 posts/24h (rolling) |
| 이미지 포맷 | JPEG만 (PNG 거부) |
| 발행 프로세스 | 2단계 (Container → Publish) |
| 계정 타입 | Business/Creator만 |
