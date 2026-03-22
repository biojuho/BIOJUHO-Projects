# Set Up Sentry Error Tracking

**Labels**: `monitoring`, `infrastructure`
**Priority**: 📊 **Monitoring** - 1개월 내

---

## Description

Sentry를 통해 프론트엔드/백엔드 에러를 중앙에서 추적합니다.

---

## Tasks

- [ ] Sentry 프로젝트 5개 생성 (biolinker, agriguard, frontend, dailynews, shared)
- [ ] Python SDK 통합 (FastAPI)
- [ ] JavaScript SDK 통합 (React)
- [ ] 환경별 분리 (dev/staging/prod)
- [ ] 성능 모니터링 활성화 (Transactions)
- [ ] 알림 채널 설정 (Slack/Telegram)
- [ ] Error Grouping 설정
- [ ] Release Tracking 설정

---

## Integration

### Python (FastAPI)

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("ENV", "development"),
    traces_sample_rate=0.1,  # 10% 성능 모니터링
    integrations=[FastApiIntegration()],
)
```

### JavaScript (React)

```javascript
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN,
  environment: import.meta.env.MODE,
  integrations: [
    new Sentry.BrowserTracing(),
    new Sentry.Replay(),
  ],
  tracesSampleRate: 0.1,
  replaysSessionSampleRate: 0.1,
});
```

---

## Acceptance Criteria

- ✅ 5개 프로젝트에 Sentry 통합 완료
- ✅ 에러가 Sentry 대시보드에 표시됨
- ✅ 알림이 Slack/Telegram으로 전송됨
- ✅ 성능 모니터링 데이터 수집됨

---

**Estimated Time**: 2-3일
