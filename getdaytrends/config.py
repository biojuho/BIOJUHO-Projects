"""
getdaytrends v2.4 - Configuration Management
환경변수 로드, 기본값, 유효성 검사를 중앙 관리.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

VERSION = "4.1"

COUNTRY_MAP = {
    "korea": "korea",
    "kr": "korea",
    "us": "united-states",
    "usa": "united-states",
    "uk": "united-kingdom",
    "uae": "united-arab-emirates",
    "india": "india",
    "in": "india",
    "japan": "japan",
    "jp": "japan",
    "global": "",
    "world": "",
}


@dataclass
class AppConfig:
    # LLM은 shared.llm 모듈에서 관리 (루트 .env에서 키 로딩)

    # Storage: Notion
    notion_token: str = ""
    notion_database_id: str = ""

    # Storage: Google Sheets
    google_service_json: str = "credentials.json"
    google_sheet_id: str = ""

    # Storage type: "notion", "google_sheets", "both", "none"
    storage_type: str = "notion"

    # Storage: Database
    # SQLite 기본. PostgreSQL 전환: DATABASE_URL=postgresql://user:pw@host/db
    db_path: str = "data/getdaytrends.db"
    database_url: str = ""          # 설정 시 PostgreSQL 사용 (SQLite 무시)

    # Schedule
    schedule_minutes: int = 360

    # Tone
    tone: str = "친근하고 위트 있는 동네 친구"
    editorial_profile: str = "report"   # 장문/Threads/블로그용 편집 프로필

    # Multi-source API keys
    twitter_bearer_token: str = ""
    # X OAuth 2.0 (포스팅용): PKCE 플로우로 발급한 유저 액세스 토큰
    x_access_token: str = ""        # 트윗 게시용 OAuth 2.0 Bearer
    x_client_id: str = ""           # X Developer App Client ID
    x_client_secret: str = ""       # X Developer App Client Secret

    # Alerts
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    alert_threshold: int = 70

    # v2.4 기능 플래그
    enable_clustering: bool = True
    enable_long_form: bool = True
    enable_threads: bool = True
    smart_schedule: bool = True
    night_mode: bool = True
    long_form_min_score: int = 95   # 이상만 장문 생성 (Sonnet 비용 절감) [C1: 90→95]
    thread_min_score: int = 999     # 쓰레드 비활성화 (비용 절감)
    threads_min_score: int = 65     # 이상만 Meta Threads 생성
    min_viral_score: int = 60       # 품질 필터: 미만이면 콘텐츠 생성 건너뜀 [기존 55 → 60]
    max_workers: int = 10           # 동시 HTTP 요청 수 [기존 6 → 10]
    daily_budget_usd: float = 3.0   # 일 예산 상한 ($). 초과 시 Sonnet 자동 비활성화 [v13.0: $2→$3]
    # 카테고리별 LLM 티어 라우팅: 해당 카테고리만 Sonnet(HEAVY) 사용, 나머지는 Haiku
    heavy_categories: list = field(default_factory=lambda: [
        "정치", "경제", "테크", "사회", "국제", "과학", "의학", "법률"
    ])
    # [C2] 시간대별 예산: 비피크 시간(야간/새벽) 예산 비율 (1.0=동일, 0.5=절반)
    peak_budget_multiplier: float = 0.5    # off-peak(22~07시) 예산 = daily * 0.5
    cost_alert_pct: float = 70.0               # 일일 예산의 70% 도달 시 경고

    # ===================================================
    # [v2.5] High-Quality / Transcreation
    # ===================================================
    target_languages: list[str] = field(default_factory=lambda: ["ko"])  # 트랜스크리에이션 대상 언어

    # Canva API Integration
    canva_api_key: str = ""
    canva_client_id: str = ""
    canva_client_secret: str = ""
    canva_template_id: str = ""

    # ===================================================
    # [v3.0] 품질·최적화·고도화
    # ===================================================
    # Phase 1: 신뢰성
    cache_volume_bucket: int = 5000        # 핑거프린트 볼륨 버킷 크기 (작을수록 정밀)
    data_retention_days: int = 90          # DB 데이터 보존 기간 (일)
    notion_sem_limit: int = 10             # Notion 동시 저장 최대 세마포어 수

    # Phase 3: 관측 가능성
    enable_structured_metrics: bool = True  # 파이프라인 완료 후 JSON 구조화 메트릭 로깅

    # Phase 4: 고도화
    enable_sentiment_filter: bool = True   # 유해 트렌드 자동 필터 (safety_flag=True 스킵)
    enable_ab_variants: bool = False       # A/B 변형 생성 (tone 다양화, Haiku 추가 1회 호출)
    enable_multilang: bool = False         # 멀티언어 생성 (target_languages 언어 수만큼 추가 생성)

    # ===================================================
    # [v4.0] 트렌드 검증 & 하이브리드 스코어링
    # ===================================================
    # Phase 1: 멀티소스 교차 검증
    min_cross_source_confidence: int = 2   # 이 점수(0~4) 미만이면 viral_potential 65% 패널티
    # Phase 2: 하이브리드 스코어링 가중치
    viral_score_llm_weight: float = 0.6    # LLM 점수 비중 (나머지는 시그널 점수)
    # Phase 3: 히스토리 패턴 보정
    enable_history_correction: bool = True # 반복·하락 트렌드 자동 점수 보정
    # Phase 4: 중연 킥 포인트
    joongyeon_kick_long_form_threshold: int = 75  # 이상이면 장문 min_score 우회 생성

    # ===================================================
    # [v5.0] 소스 품질 피드백 + YouTube
    # ===================================================
    enable_youtube_trending: bool = False          # YouTube Trending RSS (폐기됨, 기본 비활성)
    enable_source_quality_tracking: bool = True    # 소스 품질 DB 기록 활성화
    news_rss_max_items: int = 5                    # Google News RSS 최대 수집 수

    # ===================================================
    # [v6.0] 품질 피드백 루프 + 카테고리 다양성
    # ===================================================
    min_article_count: int = 3                     # 파이프라인 최소 기사 수 보장 [v13.0: 5→3, 저품질 강제포함 방지]
    max_same_category: int = 2                     # 동일 카테고리 최대 기사 수
    enable_quality_feedback: bool = True            # 생성 후 LLM 품질 검증 활성화
    quality_feedback_min_score: int = 50            # QA 점수 이 미만이면 재생성
    threads_quality_min_score: int = 65             # Threads QA 최소 점수
    long_form_quality_min_score: int = 70           # X 장문 QA 최소 점수
    blog_quality_min_score: int = 75                # 네이버 블로그 QA 최소 점수

    # ===================================================
    # [v6.1] 최신성 검증 (Freshness Validation)
    # ===================================================
    max_content_age_hours: int = 24                # 이 시간 초과 트렌드는 expired 등급
    freshness_penalty_stale: float = 0.85          # stale (6~12h) 패널티 배율
    freshness_penalty_expired: float = 0.7         # expired (12h+) 패널티 배율

    # ===================================================
    # [v7.0] 카테고리 제외 필터
    # ===================================================
    exclude_categories: list[str] = field(default_factory=lambda: [
        "정치", "연예"
    ])  # 이 카테고리의 트렌드를 파이프라인에서 자동 제외

    # ===================================================
    # [v8.0] 계정 정체성 (프롬프트 ②: 멘션 작성 컨텍스트)
    # ===================================================
    account_niche: str = "AI·테크·트렌드"          # 계정 분야
    target_audience: str = "IT 종사자, 스타트업 관계자, 테크 트렌드에 관심있는 직장인"  # 타겟 오디언스

    # ===================================================
    # [v9.0] Phase A: 비용 최적화
    # ===================================================
    enable_llm_clustering: bool = False        # False=로컬 Jaccard 클러스터링 (LLM 호출 절감)
    jaccard_cluster_threshold: float = 0.35   # 로컬 클러스터링 유사도 임계값
    # [v14.0] Gemini Embedding 2 의미적 클러스터링
    enable_embedding_clustering: bool = True   # True=Gemini Embedding 기반 의미적 유사도 (Jaccard 자동 폴백)
    embedding_cluster_threshold: float = 0.75  # 코사인 유사도 임계값 (0.0~1.0, 높을수록 엄격)
    qa_skip_cached: bool = True               # 캐시 재사용 콘텐츠 QA 스킵
    qa_skip_high_score: int = 85              # 이 점수 이상 트렌드 QA 스킵
    qa_skip_categories: list[str] = field(default_factory=lambda: ["날씨", "음식", "스포츠"])
    generation_mode_override: str = ""        # "" = auto | "full" = 장문 포함 | "lite" = 단문만

    # ===================================================
    # [v10.0] Phase 1: 컨텍스트 강화
    # ===================================================
    require_context: bool = True             # True=컨텍스트 없으면 생성 안 함 (필수화)
    cache_ttl_rising: int = 2                # 상승중 트렌드 캐시 TTL (시간)
    cache_ttl_peak: int = 6                  # 정점 트렌드 캐시 TTL (시간)
    cache_ttl_falling: int = 18              # 하락중 트렌드 캐시 TTL (시간)
    cache_ttl_default: int = 12              # 미분류 캐시 TTL (시간)

    # ===================================================
    # [v9.0] Phase B: 품질 최적화
    # ===================================================
    watchlist_keywords: list[str] = field(default_factory=list)  # 관심 키워드 (쉼표 구분)
    enable_content_diversity: bool = True     # 이전 생성 표현을 프롬프트에 주입해 중복 방지
    content_diversity_hours: int = 24         # 이전 트윗 조회 범위 (시간)
    enable_velocity_scoring: bool = True      # 볼륨 상승 속도 지표 신호 점수 반영

    # ===================================================
    # [v9.0] Phase C: 이머징 트렌드 예측
    # ===================================================
    enable_emerging_detection: bool = True    # 저볼륨+고벨로시티 이머징 감지 활성화
    emerging_velocity_threshold: float = 2.0  # 이 배율 이상이면 이머징 후보
    emerging_volume_cap: int = 5000           # 이 볼륨 이하만 이머징 후보

    # ===================================================
    # [v12.0] 멀티플랫폼 콘텐츠 운영
    # ===================================================
    target_platforms: list[str] = field(default_factory=lambda: ["x", "threads"])  # [v13.0] naver_blog 제거 (X/Threads만)
    content_hub_database_id: str = ""   # 멀티플랫폼 Content Hub 노션 DB ID
    blog_min_score: int = 70            # 이 점수 이상만 네이버 블로그 글감 생성
    blog_min_words: int = 2000          # 네이버 블로그 최소 글자 수
    blog_max_words: int = 5000          # 네이버 블로그 최대 글자 수
    blog_seo_keywords_count: int = 5    # SEO 키워드 추천 수

    # ===================================================
    # [v15.0] Phase A: Zero Content Prevention + Niche Scoring
    # ===================================================
    enable_zero_content_prevention: bool = True   # 모든 트렌드가 제외 카테고리일 때 최소 1개 보장
    niche_categories: list[str] = field(default_factory=lambda: ["테크", "경제"])  # 니치 보너스 대상 카테고리
    niche_bonus_points: int = 10                  # 니치 카테고리 보너스 점수
    enable_lazy_context: bool = True              # 지연 컨텍스트 로딩 활성화

    # ===================================================
    # [v15.0] Phase B: Content Diversity + Persona Rotation
    # ===================================================
    diversity_sim_threshold: float = 0.85         # 콘텐츠 유사도 임계값 (이상이면 중복 판정)
    persona_rotation: str = "category"            # 퍼소나 선택 모드: category | round_robin | fixed
    persona_pool: list[str] = field(default_factory=lambda: ["joongyeon", "analyst", "storyteller"])

    # ===================================================
    # [v16.0] MARL Pipeline Integration
    # ===================================================
    enable_marl_generation: bool = False           # MARL 강화 생성 활성화 (high-value 트렌드 전용)
    marl_min_viral_score: int = 80                 # 이 점수 이상만 MARL 적용
    marl_stages: int = 3                           # MARL 파이프라인 단계 수 (3=생성+비평+수정, 5=전체)
    marl_daily_budget_cap_usd: float = 0.05        # MARL 일일 추가 예산 상한 ($)

    # ===================================================
    # [v17.0] NotebookLM Integration
    # ===================================================
    enable_notebooklm: bool = False                # NotebookLM 자동 연동 활성화
    notebooklm_min_viral_score: int = 75           # 이 점수 이상만 NotebookLM 노트북 생성
    notebooklm_content_types: list[str] = field(default_factory=list)  # 생성 콘텐츠 유형 (빈값=AI분석만, audio/slide-deck/mind-map 등)
    notebooklm_max_notebooks: int = 3              # 런당 최대 노트북 생성 수

    # ===================================================
    # [v5.0] B. Adaptive Voice — 성과 기반 패턴 가중치
    # ===================================================
    enable_adaptive_voice: bool = True             # 훅/킥 패턴별 성과 가중치 프롬프트 주입
    pattern_weight_min_samples: int = 3            # 가중치 계산 최소 샘플 수
    pattern_weight_days: int = 30                  # 가중치 계산 기간 (일)

    # ===================================================
    # [v5.0] D. Real-time Signal — 3단계 수집
    # ===================================================
    enable_tiered_collection: bool = True          # 3단계 수집 활성화 (1h/6h/48h)
    early_signal_boost_threshold: float = 2.0      # 초기 ER이 평균의 N배 이상이면 후속 콘텐츠 트리거
    early_signal_suppress_threshold: float = 0.3   # 초기 ER이 평균의 N배 이하이면 앵글 가중치 하향

    # ===================================================
    # [v5.0] E. Benchmark QA — 골든 레퍼런스
    # ===================================================
    enable_golden_reference_qa: bool = True        # 골든 레퍼런스 기반 비교 평가 QA
    golden_reference_limit: int = 3                # QA 프롬프트에 주입할 레퍼런스 수
    golden_reference_auto_update_days: int = 7     # 자동 갱신 조회 기간 (일)

    # ===================================================
    # [v5.0] A. Trend Genealogy — 트렌드 계보 분석
    # ===================================================
    enable_trend_genealogy: bool = True            # 트렌드 계보 분석 활성화
    genealogy_history_hours: int = 72              # 계보 히스토리 조회 기간 (시간)
    genealogy_min_confidence: float = 0.5          # 계보 연결 최소 확신도

    # ===================================================
    # [v6.0] 정보 정확성 검증
    # ===================================================
    enable_fact_checking: bool = True              # 생성 콘텐츠 팩트 체크 활성화
    fact_check_min_accuracy: float = 0.6           # 팩트 체크 최소 정확도 (0~1, 미만이면 재생성)
    fact_check_strict_mode: bool = False            # True면 인용/비교도 엄격 검증
    enable_source_credibility: bool = True          # 출처 신뢰도 가중치 적용
    credibility_penalty_threshold: float = 0.3      # 이 신뢰도 미만이면 viral_potential 패널티
    credibility_penalty_factor: float = 0.85        # 저신뢰 출처 패널티 배율
    enable_cross_source_consistency: bool = True     # 소스 간 일관성 검증 활성화
    hallucination_zero_tolerance: bool = True        # True면 환각 감지 시 무조건 재생성

    # Runtime options (CLI overrides)
    country: str = "korea"
    countries: list = field(default_factory=list)   # 다국가 실행 목록
    limit: int = 10
    dedupe_window_hours: int = 6
    one_shot: bool = False
    dry_run: bool = False
    verbose: bool = False
    no_alerts: bool = False

    def __post_init__(self):
        if not self.countries:
            self.countries = [self.country]

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            notion_token=os.getenv("NOTION_TOKEN", ""),
            notion_database_id=os.getenv("NOTION_DATABASE_ID", ""),
            google_service_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials.json"),
            google_sheet_id=os.getenv("GOOGLE_SHEET_ID", ""),
            storage_type=os.getenv("STORAGE_TYPE", "notion").lower(),
            db_path=os.getenv("DB_PATH", "data/getdaytrends.db"),
            database_url=os.getenv("DATABASE_URL", ""),
            schedule_minutes=int(os.getenv("SCHEDULE_INTERVAL_MINUTES", "360")),
            tone=os.getenv("TONE", "친근하고 위트 있는 동네 친구"),
            editorial_profile=os.getenv("EDITORIAL_PROFILE", "report").lower(),
            twitter_bearer_token=os.getenv("TWITTER_BEARER_TOKEN", ""),
            x_access_token=os.getenv("X_ACCESS_TOKEN", ""),
            x_client_id=os.getenv("X_CLIENT_ID", ""),
            x_client_secret=os.getenv("X_CLIENT_SECRET", ""),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
            alert_threshold=int(os.getenv("ALERT_THRESHOLD", "70")),
            enable_clustering=os.getenv("ENABLE_CLUSTERING", "true").lower() == "true",
            enable_long_form=os.getenv("ENABLE_LONG_FORM", "true").lower() == "true",
            enable_threads=os.getenv("ENABLE_THREADS", "true").lower() == "true",
            smart_schedule=os.getenv("SMART_SCHEDULE", "true").lower() == "true",
            night_mode=os.getenv("NIGHT_MODE", "true").lower() == "true",
            long_form_min_score=int(os.getenv("LONG_FORM_MIN_SCORE", "95")),
            thread_min_score=int(os.getenv("THREAD_MIN_SCORE", "92")),
            threads_min_score=int(os.getenv("THREADS_MIN_SCORE", "65")),
            min_viral_score=int(os.getenv("MIN_VIRAL_SCORE", "60")),
            max_workers=int(os.getenv("MAX_WORKERS", "10")),
            daily_budget_usd=float(os.getenv("DAILY_BUDGET_USD", "3.0")),
            heavy_categories=[
                c.strip()
                for c in os.getenv("HEAVY_CATEGORIES", "정치,경제,테크,사회,국제,과학,의학,법률").split(",")
                if c.strip()
            ],
            country=os.getenv("DEFAULT_COUNTRY", "korea"),
            limit=int(os.getenv("DEFAULT_LIMIT", "10")),
            dedupe_window_hours=int(os.getenv("DEDUPE_WINDOW_HOURS", "6")),
            peak_budget_multiplier=float(os.getenv("PEAK_BUDGET_MULTIPLIER", "0.5")),
            cost_alert_pct=float(os.getenv("COST_ALERT_PCT", "70")),
            target_languages=[
                lang.strip()
                for lang in os.getenv("TARGET_LANGUAGES", "ko").split(",")
                if lang.strip()
            ],
            canva_api_key=os.getenv("CANVA_API_KEY", ""),
            canva_client_id=os.getenv("CANVA_CLIENT_ID", ""),
            canva_client_secret=os.getenv("CANVA_CLIENT_SECRET", ""),
            canva_template_id=os.getenv("CANVA_TEMPLATE_ID", ""),
            # v3.0
            cache_volume_bucket=int(os.getenv("CACHE_VOLUME_BUCKET", "5000")),
            data_retention_days=int(os.getenv("DATA_RETENTION_DAYS", "90")),
            notion_sem_limit=int(os.getenv("NOTION_SEM_LIMIT", "10")),
            enable_structured_metrics=os.getenv("ENABLE_STRUCTURED_METRICS", "true").lower() == "true",
            enable_sentiment_filter=os.getenv("ENABLE_SENTIMENT_FILTER", "true").lower() == "true",
            enable_ab_variants=os.getenv("ENABLE_AB_VARIANTS", "false").lower() == "true",
            enable_multilang=os.getenv("ENABLE_MULTILANG", "false").lower() == "true",
            # v4.0
            min_cross_source_confidence=int(os.getenv("MIN_CROSS_SOURCE_CONFIDENCE", "2")),
            viral_score_llm_weight=float(os.getenv("VIRAL_SCORE_LLM_WEIGHT", "0.6")),
            enable_history_correction=os.getenv("ENABLE_HISTORY_CORRECTION", "true").lower() == "true",
            joongyeon_kick_long_form_threshold=int(os.getenv("JOONGYEON_KICK_LONG_FORM_THRESHOLD", "75")),
            # v5.0
            enable_youtube_trending=os.getenv("ENABLE_YOUTUBE_TRENDING", "false").lower() == "true",
            enable_source_quality_tracking=os.getenv("ENABLE_SOURCE_QUALITY_TRACKING", "true").lower() == "true",
            news_rss_max_items=int(os.getenv("NEWS_RSS_MAX_ITEMS", "5")),
            # v6.0
            min_article_count=int(os.getenv("MIN_ARTICLE_COUNT", "3")),
            max_same_category=int(os.getenv("MAX_SAME_CATEGORY", "2")),
            enable_quality_feedback=os.getenv("ENABLE_QUALITY_FEEDBACK", "true").lower() == "true",
            quality_feedback_min_score=int(os.getenv("QUALITY_FEEDBACK_MIN_SCORE", "50")),
            threads_quality_min_score=int(os.getenv("THREADS_QUALITY_MIN_SCORE", "65")),
            long_form_quality_min_score=int(os.getenv("LONG_FORM_QUALITY_MIN_SCORE", "70")),
            blog_quality_min_score=int(os.getenv("BLOG_QUALITY_MIN_SCORE", "75")),
            # v6.1
            max_content_age_hours=int(os.getenv("MAX_CONTENT_AGE_HOURS", "24")),
            freshness_penalty_stale=float(os.getenv("FRESHNESS_PENALTY_STALE", "0.85")),
            freshness_penalty_expired=float(os.getenv("FRESHNESS_PENALTY_EXPIRED", "0.7")),
            # v7.0
            exclude_categories=[
                c.strip()
                for c in os.getenv("EXCLUDE_CATEGORIES", "정치,연예").split(",")
                if c.strip()
            ],
            # v8.0
            account_niche=os.getenv("ACCOUNT_NICHE", "AI·테크·트렌드"),
            target_audience=os.getenv("TARGET_AUDIENCE", "IT 종사자, 스타트업 관계자, 테크 트렌드에 관심있는 직장인"),
            # v9.0 Phase A
            enable_llm_clustering=os.getenv("ENABLE_LLM_CLUSTERING", "false").lower() == "true",
            jaccard_cluster_threshold=float(os.getenv("JACCARD_CLUSTER_THRESHOLD", "0.35")),
            # v14.0
            enable_embedding_clustering=os.getenv("ENABLE_EMBEDDING_CLUSTERING", "true").lower() == "true",
            embedding_cluster_threshold=float(os.getenv("EMBEDDING_CLUSTER_THRESHOLD", "0.75")),
            qa_skip_cached=os.getenv("QA_SKIP_CACHED", "true").lower() == "true",
            qa_skip_high_score=int(os.getenv("QA_SKIP_HIGH_SCORE", "85")),
            qa_skip_categories=[
                c.strip()
                for c in os.getenv("QA_SKIP_CATEGORIES", "날씨,음식,스포츠").split(",")
                if c.strip()
            ],
            generation_mode_override=os.getenv("GENERATION_MODE", ""),
            # v10.0 Phase 1
            require_context=os.getenv("REQUIRE_CONTEXT", "true").lower() == "true",
            cache_ttl_rising=int(os.getenv("CACHE_TTL_RISING", "2")),
            cache_ttl_peak=int(os.getenv("CACHE_TTL_PEAK", "6")),
            cache_ttl_falling=int(os.getenv("CACHE_TTL_FALLING", "18")),
            cache_ttl_default=int(os.getenv("CACHE_TTL_DEFAULT", "12")),
            # v9.0 Phase B
            watchlist_keywords=[
                k.strip()
                for k in os.getenv("WATCHLIST_KEYWORDS", "").split(",")
                if k.strip()
            ],
            enable_content_diversity=os.getenv("ENABLE_CONTENT_DIVERSITY", "true").lower() == "true",
            content_diversity_hours=int(os.getenv("CONTENT_DIVERSITY_HOURS", "24")),
            enable_velocity_scoring=os.getenv("ENABLE_VELOCITY_SCORING", "true").lower() == "true",
            # v9.0 Phase C
            enable_emerging_detection=os.getenv("ENABLE_EMERGING_DETECTION", "true").lower() == "true",
            emerging_velocity_threshold=float(os.getenv("EMERGING_VELOCITY_THRESHOLD", "2.0")),
            emerging_volume_cap=int(os.getenv("EMERGING_VOLUME_CAP", "5000")),
            # v12.0 멀티플랫폼
            target_platforms=[
                p.strip()
                for p in os.getenv("TARGET_PLATFORMS", "x").split(",")
                if p.strip()
            ],
            content_hub_database_id=os.getenv("CONTENT_HUB_DATABASE_ID", ""),
            blog_min_score=int(os.getenv("BLOG_MIN_SCORE", "70")),
            blog_min_words=int(os.getenv("BLOG_MIN_WORDS", "2000")),
            blog_max_words=int(os.getenv("BLOG_MAX_WORDS", "5000")),
            blog_seo_keywords_count=int(os.getenv("BLOG_SEO_KEYWORDS_COUNT", "5")),
            # v15.0 Phase A
            enable_zero_content_prevention=os.getenv("ENABLE_ZERO_CONTENT_PREVENTION", "true").lower() == "true",
            niche_categories=[
                c.strip()
                for c in os.getenv("NICHE_CATEGORIES", "테크,경제").split(",")
                if c.strip()
            ],
            niche_bonus_points=int(os.getenv("NICHE_BONUS_POINTS", "10")),
            enable_lazy_context=os.getenv("ENABLE_LAZY_CONTEXT", "true").lower() == "true",
            # v15.0 Phase B
            diversity_sim_threshold=float(os.getenv("DIVERSITY_SIM_THRESHOLD", "0.85")),
            persona_rotation=os.getenv("PERSONA_ROTATION", "category"),
            persona_pool=[
                p.strip()
                for p in os.getenv("PERSONA_POOL", "joongyeon,analyst,storyteller").split(",")
                if p.strip()
            ],
            # v16.0 MARL
            enable_marl_generation=os.getenv("ENABLE_MARL_GENERATION", "false").lower() == "true",
            marl_min_viral_score=int(os.getenv("MARL_MIN_VIRAL_SCORE", "80")),
            marl_stages=int(os.getenv("MARL_STAGES", "3")),
            marl_daily_budget_cap_usd=float(os.getenv("MARL_DAILY_BUDGET_CAP_USD", "0.05")),
            # v17.0 NotebookLM
            enable_notebooklm=os.getenv("ENABLE_NOTEBOOKLM", "false").lower() == "true",
            notebooklm_min_viral_score=int(os.getenv("NOTEBOOKLM_MIN_VIRAL_SCORE", "75")),
            notebooklm_content_types=[
                t.strip()
                for t in os.getenv("NOTEBOOKLM_CONTENT_TYPES", "audio").split(",")
                if t.strip()
            ],
            notebooklm_max_notebooks=int(os.getenv("NOTEBOOKLM_MAX_NOTEBOOKS", "3")),
            # v5.0 B. Adaptive Voice
            enable_adaptive_voice=os.getenv("ENABLE_ADAPTIVE_VOICE", "true").lower() == "true",
            pattern_weight_min_samples=int(os.getenv("PATTERN_WEIGHT_MIN_SAMPLES", "3")),
            pattern_weight_days=int(os.getenv("PATTERN_WEIGHT_DAYS", "30")),
            # v5.0 D. Real-time Signal
            enable_tiered_collection=os.getenv("ENABLE_TIERED_COLLECTION", "true").lower() == "true",
            early_signal_boost_threshold=float(os.getenv("EARLY_SIGNAL_BOOST_THRESHOLD", "2.0")),
            early_signal_suppress_threshold=float(os.getenv("EARLY_SIGNAL_SUPPRESS_THRESHOLD", "0.3")),
            # v5.0 E. Benchmark QA
            enable_golden_reference_qa=os.getenv("ENABLE_GOLDEN_REFERENCE_QA", "true").lower() == "true",
            golden_reference_limit=int(os.getenv("GOLDEN_REFERENCE_LIMIT", "3")),
            golden_reference_auto_update_days=int(os.getenv("GOLDEN_REFERENCE_AUTO_UPDATE_DAYS", "7")),
            # v5.0 A. Trend Genealogy
            enable_trend_genealogy=os.getenv("ENABLE_TREND_GENEALOGY", "true").lower() == "true",
            genealogy_history_hours=int(os.getenv("GENEALOGY_HISTORY_HOURS", "72")),
            genealogy_min_confidence=float(os.getenv("GENEALOGY_MIN_CONFIDENCE", "0.5")),
        )

    def validate(self) -> list[str]:
        """오류 목록 반환. 빈 리스트이면 유효."""
        from shared.llm.config import load_keys

        errors = []
        keys = load_keys()
        if not any(keys.values()):
            errors.append("LLM API 키가 설정되지 않았습니다 (루트 .env 확인).")

        if self.storage_type in ("notion", "both"):
            if not self.notion_token or "your_" in self.notion_token:
                errors.append("NOTION_TOKEN이 설정되지 않았습니다.")
            if not self.notion_database_id or "your_" in self.notion_database_id:
                errors.append("NOTION_DATABASE_ID가 설정되지 않았습니다.")

        if self.storage_type in ("google_sheets", "both"):
            if not self.google_sheet_id or "your_" in self.google_sheet_id:
                errors.append("GOOGLE_SHEET_ID가 설정되지 않았습니다.")
            if not os.path.exists(self.google_service_json):
                errors.append(f"Google 서비스 계정 JSON을 찾을 수 없습니다: {self.google_service_json}")

        # 수치 범위 검증
        valid_storage = {"notion", "google_sheets", "both", "none"}
        valid_editorial_profiles = {"report", "classic"}
        if self.storage_type not in valid_storage:
            errors.append(f"STORAGE_TYPE이 유효하지 않습니다: '{self.storage_type}' (허용: {valid_storage})")
        if self.editorial_profile not in valid_editorial_profiles:
            errors.append(
                f"EDITORIAL_PROFILE이 유효하지 않습니다: '{self.editorial_profile}' "
                f"(허용: {valid_editorial_profiles})"
            )
        if not 1 <= self.schedule_minutes <= 1440:
            errors.append(f"SCHEDULE_INTERVAL_MINUTES 범위 초과: {self.schedule_minutes} (1~1440)")
        if self.daily_budget_usd < 0:
            errors.append(f"DAILY_BUDGET_USD는 0 이상이어야 합니다: {self.daily_budget_usd}")
        if not 1 <= self.max_workers <= 50:
            errors.append(f"MAX_WORKERS 범위 초과: {self.max_workers} (1~50)")
        if not 1 <= self.limit <= 100:
            errors.append(f"DEFAULT_LIMIT 범위 초과: {self.limit} (1~100)")
        if not 1 <= self.notion_sem_limit <= 50:
            errors.append(f"NOTION_SEM_LIMIT 범위 초과: {self.notion_sem_limit} (1~50)")
        if not 1 <= self.data_retention_days <= 3650:
            errors.append(f"DATA_RETENTION_DAYS 범위 초과: {self.data_retention_days} (1~3650)")

        return errors

    def resolve_country_slug(self) -> str:
        """국가 코드를 getdaytrends.com URL 슬러그로 변환."""
        return COUNTRY_MAP.get(self.country.lower(), self.country.lower())

    def for_country(self, country: str) -> "AppConfig":
        """지정 국가로 설정을 복제해 반환 (다국가 병렬 실행용)."""
        import dataclasses
        return dataclasses.replace(self, country=country, countries=[country])

    def get_effective_budget(self) -> float:
        """[C2] 시간대별 유효 예산 반환. 비피크(22~07시) 예산 절감."""
        from datetime import datetime
        hour = datetime.now().hour
        if hour >= 22 or hour < 7:
            return self.daily_budget_usd * self.peak_budget_multiplier
        return self.daily_budget_usd

    def get_cache_ttl(self, peak_status: str = "") -> int:
        """[v10.0] peak_status 기반 동적 캐시 TTL (시간) 반환."""
        return {
            "상승중": self.cache_ttl_rising,
            "정점": self.cache_ttl_peak,
            "하락중": self.cache_ttl_falling,
        }.get(peak_status, self.cache_ttl_default)

    def get_generation_mode(self) -> str:
        """[v9.0] 시간대 기반 생성 모드 반환.
        'full': 장문 포함 전체 생성 (피크 시간)
        'lite': 단문 트윗만 (비피크)
        """
        if self.generation_mode_override in ("full", "lite"):
            return self.generation_mode_override
        from datetime import datetime
        hour = datetime.now().hour
        # 피크: 아침(7-10), 점심(12-14), 저녁(19-22)
        if hour in range(7, 11) or hour in range(12, 15) or hour in range(19, 23):
            return "full"
        return "lite"

    def get_quality_threshold(self, content_group: str) -> int:
        """콘텐츠 그룹별 QA 최소 점수 반환."""
        return {
            "tweets": self.quality_feedback_min_score,
            "threads_posts": self.threads_quality_min_score,
            "long_posts": self.long_form_quality_min_score,
            "blog_posts": self.blog_quality_min_score,
        }.get(content_group, self.quality_feedback_min_score)

    def export_stats(self) -> dict:
        """[O3] 대시보드용 설정 상태 내보내기."""
        return {
            "version": VERSION,
            "country": self.country,
            "limit": self.limit,
            "editorial_profile": self.editorial_profile,
            "daily_budget_usd": self.daily_budget_usd,
            "effective_budget": self.get_effective_budget(),
            "long_form_min_score": self.long_form_min_score,
            "thread_min_score": self.thread_min_score,
            "threads_min_score": self.threads_min_score,
            "threads_quality_min_score": self.threads_quality_min_score,
            "long_form_quality_min_score": self.long_form_quality_min_score,
            "blog_quality_min_score": self.blog_quality_min_score,
            "min_viral_score": self.min_viral_score,
            "max_workers": self.max_workers,
            "storage_type": self.storage_type,
            "features": {
                "clustering": self.enable_clustering,
                "long_form": self.enable_long_form,
                "threads": self.enable_threads,
                "smart_schedule": self.smart_schedule,
                "night_mode": self.night_mode,
                "marl_generation": self.enable_marl_generation,
                "adaptive_voice": self.enable_adaptive_voice,
                "tiered_collection": self.enable_tiered_collection,
                "golden_reference_qa": self.enable_golden_reference_qa,
                "trend_genealogy": self.enable_trend_genealogy,
                "notebooklm": self.enable_notebooklm,
            },
            "target_platforms": self.target_platforms,
        }
