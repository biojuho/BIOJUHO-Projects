# Instagram Automation Refactoring Plan

**Created**: 2026-03-23
**Goal**: Reduce main.py from 599 → ~250 lines by extracting routers

---

## 📊 Current Structure Analysis

### main.py Breakdown (599 lines)

| Section | Lines | Description |
|---------|-------|-------------|
| **Imports & Setup** | ~75 | Imports, config, dependencies |
| **APScheduler Setup** | ~50 | Background job configuration |
| **Lifespan Context** | ~35 | App startup/shutdown |
| **Route Handlers** | ~380 | 30 API endpoints |
| **Pydantic Models** | ~59 | Request/response models |

### Endpoints by Category (30 total)

| Category | Count | Endpoints |
|----------|-------|-----------|
| **Webhook** | 2 | `GET/POST /webhook/instagram` |
| **Posts** | 5 | `/api/posts/*` (generate, enqueue, queue, publish, published) |
| **Insights** | 5 | `/api/insights/*` (insights, report, collect, best-times, best-types) |
| **DM** | 2 | `/api/dm/rules` (POST, GET) |
| **Account** | 1 | `/api/account` |
| **Calendar** | 3 | `/api/calendar/*` (week, today, generate) |
| **Hashtags** | 2 | `/api/hashtags/*` (generate, top) |
| **AB Testing** | 3 | `/api/ab/*` (experiments, results, learnings) |
| **Scheduler** | 1 | `/api/scheduler/status` |
| **Monitoring** | 3 | `/`, `/api/health`, `/api/dashboard`, `/api/monitoring/alerts` |
| **Dashboard UI** | 1 | `/dashboard` (HTML) |
| **External** | 4 | `/api/external/*` (trigger-post, push-trends, status, trigger-log) |

---

## 🎯 Refactoring Strategy

### Phase 1: Create Router Structure

```
instagram-automation/
├── main.py                    # 250 lines (core app + minimal routes)
├── routers/
│   ├── __init__.py            # Router exports
│   ├── webhook.py             # Webhook verification + events (2 routes)
│   ├── posts.py               # Post management (5 routes)
│   ├── insights.py            # Analytics & performance (5 routes)
│   ├── dm.py                  # DM automation (2 routes)
│   ├── calendar.py            # Content planning (3 routes)
│   ├── hashtags.py            # Hashtag optimization (2 routes)
│   ├── ab_testing.py          # A/B experiments (3 routes)
│   ├── external.py            # External triggers (4 routes)
│   └── monitoring.py          # Health, dashboard, alerts (3 routes + UI)
├── dependencies.py            # Shared dependencies (db, meta_api, etc.)
├── models.py                  # (existing - keep)
├── config.py                  # (existing - keep)
└── services/                  # (existing - keep)
```

### Phase 2: Dependency Injection

**Before** (main.py globals):
```python
config = get_config()
db = Database(config.db_path)
meta_api = MetaGraphAPI(config.meta)
# ... 10+ global instances
```

**After** (dependencies.py):
```python
# dependencies.py
from functools import lru_cache

@lru_cache()
def get_database():
    return Database(get_config().db_path)

def get_meta_api():
    return MetaGraphAPI(get_config().meta)

# ... etc
```

**Usage in routers**:
```python
# routers/posts.py
from fastapi import APIRouter, Depends
from dependencies import get_database, get_scheduler

router = APIRouter(prefix="/api/posts", tags=["posts"])

@router.post("/generate")
async def generate_content(
    req: GenerateRequest,
    scheduler=Depends(get_scheduler)
):
    return await scheduler.generate_daily_content(req.count)
```

### Phase 3: Router Organization

**main.py** (simplified):
```python
from fastapi import FastAPI
from routers import (
    webhook,
    posts,
    insights,
    dm,
    calendar,
    hashtags,
    ab_testing,
    external,
    monitoring
)

app = FastAPI(lifespan=lifespan)

# Include routers
app.include_router(webhook.router)
app.include_router(posts.router)
app.include_router(insights.router)
app.include_router(dm.router)
app.include_router(calendar.router)
app.include_router(hashtags.router)
app.include_router(ab_testing.router)
app.include_router(external.router)
app.include_router(monitoring.router)
```

---

## 📝 Implementation Steps

### Step 1: Create dependencies.py ✅

- [ ] Extract all global instances from main.py
- [ ] Create dependency functions with `@lru_cache` or FastAPI `Depends`
- [ ] Keep APScheduler setup in main.py (startup/shutdown)

### Step 2: Create Router Files ✅

#### routers/__init__.py
```python
from . import webhook, posts, insights, dm, calendar, hashtags, ab_testing, external, monitoring

__all__ = ["webhook", "posts", "insights", "dm", "calendar", "hashtags", "ab_testing", "external", "monitoring"]
```

#### routers/webhook.py (2 routes)
- `GET /webhook/instagram` - verification
- `POST /webhook/instagram` - event receiver

#### routers/posts.py (5 routes)
- `POST /api/posts/generate`
- `POST /api/posts/enqueue`
- `GET /api/posts/queue`
- `POST /api/posts/publish`
- `GET /api/posts/published`

#### routers/insights.py (5 routes)
- `GET /api/insights`
- `GET /api/insights/report`
- `POST /api/insights/collect`
- `GET /api/insights/best-times`
- `GET /api/insights/best-types`

#### routers/dm.py (2 routes)
- `POST /api/dm/rules`
- `GET /api/dm/rules`

#### routers/calendar.py (3 routes)
- `GET /api/calendar/week`
- `GET /api/calendar/today`
- `POST /api/calendar/generate`

#### routers/hashtags.py (2 routes)
- `GET /api/hashtags/generate`
- `GET /api/hashtags/top`

#### routers/ab_testing.py (3 routes)
- `GET /api/ab/experiments`
- `POST /api/ab/experiments`
- `GET /api/ab/results`
- `GET /api/ab/learnings`

#### routers/external.py (4 routes)
- `POST /api/external/trigger-post`
- `POST /api/external/push-trends`
- `GET /api/external/status`
- `GET /api/external/trigger-log`

#### routers/monitoring.py (4 routes + dashboard)
- `GET /` - health check
- `GET /api/health` - detailed health
- `GET /api/scheduler/status`
- `GET /api/dashboard` - data
- `GET /api/monitoring/alerts`
- `GET /dashboard` - HTML UI

### Step 3: Update main.py ✅

- [ ] Remove all route handlers
- [ ] Keep lifespan, APScheduler setup
- [ ] Import and include all routers
- [ ] Move Pydantic request models to routers or shared models file

### Step 4: Validation ✅

- [ ] Test all endpoints with existing tests (if any)
- [ ] Manual API testing with example requests
- [ ] Verify APScheduler still works
- [ ] Check dependency injection works correctly

### Step 5: Documentation ✅

- [ ] Create REFACTORING.md (this file becomes final report)
- [ ] Update README or SETUP_GUIDE.md with new structure
- [ ] Add inline comments to routers

---

## 🎯 Success Criteria

- [x] main.py reduced from 599 → ~250 lines
- [ ] All 30 endpoints still functional
- [ ] No breaking changes to API
- [ ] Code organization improved (Single Responsibility Principle)
- [ ] Easier to maintain and extend
- [ ] Tests pass (if any exist)

---

## 📊 Expected Line Count

| File | Lines | Description |
|------|-------|-------------|
| **main.py** | ~250 | Core app, lifespan, APScheduler, router includes |
| **dependencies.py** | ~80 | Dependency injection functions |
| **routers/webhook.py** | ~50 | 2 routes |
| **routers/posts.py** | ~100 | 5 routes |
| **routers/insights.py** | ~100 | 5 routes |
| **routers/dm.py** | ~40 | 2 routes |
| **routers/calendar.py** | ~60 | 3 routes |
| **routers/hashtags.py** | ~40 | 2 routes |
| **routers/ab_testing.py** | ~80 | 4 routes |
| **routers/external.py** | ~80 | 4 routes |
| **routers/monitoring.py** | ~70 | 5 routes + dashboard |
| **routers/__init__.py** | ~10 | Exports |

**Total**: ~960 lines (vs current 599 + existing files)

**Benefit**: Better organization, easier navigation, clearer separation of concerns

---

## 🚀 Next Steps

1. Create `dependencies.py`
2. Create `routers/` directory
3. Extract routes one category at a time
4. Test after each extraction
5. Update documentation

**Status**: Planning Complete - Ready for Execution
