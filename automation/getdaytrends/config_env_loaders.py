"""
getdaytrends — Environment Variable Loaders for AppConfig.
config.py에서 분리됨. AppConfig.from_env()에서 호출됩니다.
"""

import os


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def storage_env() -> dict:
    """Storage 관련 환경변수 로딩."""
    return dict(
        notion_token=os.getenv("NOTION_TOKEN", ""),
        notion_database_id=os.getenv("NOTION_DATABASE_ID", ""),
        google_service_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials.json"),
        google_sheet_id=os.getenv("GOOGLE_SHEET_ID", ""),
        storage_type=os.getenv("STORAGE_TYPE", "notion").lower(),
        db_path=os.getenv("DB_PATH", "data/getdaytrends.db"),
        database_url=os.getenv("DATABASE_URL", ""),
        cache_volume_bucket=int(os.getenv("CACHE_VOLUME_BUCKET", "5000")),
        data_retention_days=int(os.getenv("DATA_RETENTION_DAYS", "90")),
        notion_sem_limit=int(os.getenv("NOTION_SEM_LIMIT", "10")),
    )


def schedule_env() -> dict:
    """스케줄/병렬처리 관련 환경변수 로딩."""
    return dict(
        schedule_minutes=int(os.getenv("SCHEDULE_INTERVAL_MINUTES", "360")),
        enable_parallel_countries=os.getenv("ENABLE_PARALLEL_COUNTRIES", "true").lower() == "true",
        country_parallel_limit=int(os.getenv("COUNTRY_PARALLEL_LIMIT", "3")),
        country=os.getenv("DEFAULT_COUNTRY", "korea"),
        limit=int(os.getenv("DEFAULT_LIMIT", "10")),
        dedupe_window_hours=int(os.getenv("DEDUPE_WINDOW_HOURS", "6")),
        max_workers=int(os.getenv("MAX_WORKERS", "10")),
    )


def api_keys_env() -> dict:
    """외부 API 키 관련 환경변수 로딩."""
    return dict(
        twitter_bearer_token=os.getenv("TWITTER_BEARER_TOKEN", ""),
        x_access_token=os.getenv("X_ACCESS_TOKEN", ""),
        x_client_id=os.getenv("X_CLIENT_ID", ""),
        x_client_secret=os.getenv("X_CLIENT_SECRET", ""),
        twikit_username=os.getenv("TWIKIT_USERNAME", ""),
        twikit_email=os.getenv("TWIKIT_EMAIL", ""),
        twikit_password=os.getenv("TWIKIT_PASSWORD", ""),
        stripe_secret_key=os.getenv("STRIPE_SECRET_KEY", ""),
        stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET", ""),
        canva_api_key=os.getenv("CANVA_API_KEY", ""),
        canva_client_id=os.getenv("CANVA_CLIENT_ID", ""),
        canva_client_secret=os.getenv("CANVA_CLIENT_SECRET", ""),
        canva_template_id=os.getenv("CANVA_TEMPLATE_ID", ""),
    )


def alerts_env() -> dict:
    """알림 채널 관련 환경변수 로딩."""
    return dict(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL", ""),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        alert_email=os.getenv("ALERT_EMAIL", ""),
        alert_threshold=int(os.getenv("ALERT_THRESHOLD", "70")),
    )


def feature_flags_env() -> dict:
    """기능 플래그 환경변수 로딩."""
    return dict(
        enable_clustering=os.getenv("ENABLE_CLUSTERING", "true").lower() == "true",
        enable_long_form=os.getenv("ENABLE_LONG_FORM", "true").lower() == "true",
        enable_threads=os.getenv("ENABLE_THREADS", "true").lower() == "true",
        smart_schedule=os.getenv("SMART_SCHEDULE", "true").lower() == "true",
        night_mode=os.getenv("NIGHT_MODE", "true").lower() == "true",
        enable_structured_metrics=os.getenv("ENABLE_STRUCTURED_METRICS", "true").lower() == "true",
        enable_sentiment_filter=os.getenv("ENABLE_SENTIMENT_FILTER", "true").lower() == "true",
        enable_canva_visuals=os.getenv("ENABLE_CANVA_VISUALS", "false").lower() == "true",
        enable_source_quality_tracking=os.getenv("ENABLE_SOURCE_QUALITY_TRACKING", "true").lower() == "true",
        enable_quality_feedback=os.getenv("ENABLE_QUALITY_FEEDBACK", "true").lower() == "true",
        enable_history_correction=os.getenv("ENABLE_HISTORY_CORRECTION", "true").lower() == "true",
        enable_content_diversity=os.getenv("ENABLE_CONTENT_DIVERSITY", "true").lower() == "true",
        enable_velocity_scoring=os.getenv("ENABLE_VELOCITY_SCORING", "true").lower() == "true",
        enable_emerging_detection=os.getenv("ENABLE_EMERGING_DETECTION", "true").lower() == "true",
        enable_adaptive_voice=os.getenv("ENABLE_ADAPTIVE_VOICE", "true").lower() == "true",
        enable_tiered_collection=os.getenv("ENABLE_TIERED_COLLECTION", "true").lower() == "true",
        enable_golden_reference_qa=os.getenv("ENABLE_GOLDEN_REFERENCE_QA", "true").lower() == "true",
        enable_fact_checking=os.getenv("ENABLE_FACT_CHECKING", "true").lower() == "true",
        enable_trend_genealogy=os.getenv("ENABLE_TREND_GENEALOGY", "true").lower() == "true",
        enable_zero_content_prevention=os.getenv("ENABLE_ZERO_CONTENT_PREVENTION", "true").lower() == "true",
        enable_lazy_context=os.getenv("ENABLE_LAZY_CONTEXT", "true").lower() == "true",
        enable_embedding_clustering=os.getenv("ENABLE_EMBEDDING_CLUSTERING", "true").lower() == "true",
        require_context=os.getenv("REQUIRE_CONTEXT", "true").lower() == "true",
        enable_content_hub=_env_flag("ENABLE_CONTENT_HUB", default=False),
        # v16.0 EDAPE + TAP + Streaming
        enable_edape=os.getenv("ENABLE_EDAPE", "true").lower() == "true",
        edape_lookback_days=int(os.getenv("EDAPE_LOOKBACK_DAYS", "7")),
        edape_max_suppression_ratio=float(os.getenv("EDAPE_MAX_SUPPRESSION_RATIO", "0.3")),
        enable_tap=os.getenv("ENABLE_TAP", "true").lower() == "true",
        tap_lookback_hours=int(os.getenv("TAP_LOOKBACK_HOURS", "12")),
        tap_min_viral_score=int(os.getenv("TAP_MIN_VIRAL_SCORE", "60")),
        tap_snapshot_max_age_minutes=int(os.getenv("TAP_SNAPSHOT_MAX_AGE_MINUTES", "30")),
        tap_board_limit=int(os.getenv("TAP_BOARD_LIMIT", "10")),
        tap_teaser_count=int(os.getenv("TAP_TEASER_COUNT", "3")),
        enable_tap_alert_queue=os.getenv("ENABLE_TAP_ALERT_QUEUE", "true").lower() == "true",
        tap_alert_top_k=int(os.getenv("TAP_ALERT_TOP_K", "3")),
        tap_alert_min_priority=float(os.getenv("TAP_ALERT_MIN_PRIORITY", "80")),
        tap_alert_min_viral_score=int(os.getenv("TAP_ALERT_MIN_VIRAL_SCORE", "75")),
        enable_tap_alert_dispatch=os.getenv("ENABLE_TAP_ALERT_DISPATCH", "false").lower() == "true",
        tap_alert_dispatch_batch_size=int(os.getenv("TAP_ALERT_DISPATCH_BATCH_SIZE", "5")),
        tap_alert_cooldown_minutes=int(os.getenv("TAP_ALERT_COOLDOWN_MINUTES", "180")),
        enable_streaming_pipeline=os.getenv("ENABLE_STREAMING_PIPELINE", "false").lower() == "true",
        streaming_generator_concurrency=int(os.getenv("STREAMING_GENERATOR_CONCURRENCY", "3")),
        streaming_stage_timeout=int(os.getenv("STREAMING_STAGE_TIMEOUT", "120")),
    )


def quality_env() -> dict:
    """품질 관련 환경변수 로딩."""
    return dict(
        min_viral_score=int(os.getenv("MIN_VIRAL_SCORE", "60")),
        long_form_min_score=int(os.getenv("LONG_FORM_MIN_SCORE", "95")),
        thread_min_score=int(os.getenv("THREAD_MIN_SCORE", "92")),
        threads_min_score=int(os.getenv("THREADS_MIN_SCORE", "65")),
        canva_min_score=int(os.getenv("CANVA_MIN_SCORE", "90")),
        quality_feedback_min_score=int(os.getenv("QUALITY_FEEDBACK_MIN_SCORE", "50")),
        threads_quality_min_score=int(os.getenv("THREADS_QUALITY_MIN_SCORE", "65")),
        long_form_quality_min_score=int(os.getenv("LONG_FORM_QUALITY_MIN_SCORE", "70")),
        blog_quality_min_score=int(os.getenv("BLOG_QUALITY_MIN_SCORE", "75")),
        fact_check_min_accuracy=float(os.getenv("FACT_CHECK_MIN_ACCURACY", "0.6")),
        fact_check_strict_mode=os.getenv("FACT_CHECK_STRICT_MODE", "false").lower() == "true",
        hallucination_zero_tolerance=os.getenv("HALLUCINATION_ZERO_TOLERANCE", "true").lower() == "true",
        min_article_count=int(os.getenv("MIN_ARTICLE_COUNT", "3")),
        max_same_category=int(os.getenv("MAX_SAME_CATEGORY", "2")),
        max_content_age_hours=int(os.getenv("MAX_CONTENT_AGE_HOURS", "24")),
        freshness_penalty_stale=float(os.getenv("FRESHNESS_PENALTY_STALE", "0.85")),
        freshness_penalty_expired=float(os.getenv("FRESHNESS_PENALTY_EXPIRED", "0.7")),
        qa_skip_cached=os.getenv("QA_SKIP_CACHED", "true").lower() == "true",
        qa_skip_high_score=int(os.getenv("QA_SKIP_HIGH_SCORE", "85")),
        qa_skip_categories=[
            c.strip() for c in os.getenv("QA_SKIP_CATEGORIES", "\ub0a0\uc528,\uc74c\uc2dd,\uc2a4\ud3ec\uce20").split(",") if c.strip()
        ],
        golden_reference_limit=int(os.getenv("GOLDEN_REFERENCE_LIMIT", "3")),
        golden_reference_auto_update_days=int(os.getenv("GOLDEN_REFERENCE_AUTO_UPDATE_DAYS", "7")),
        diversity_sim_threshold=float(os.getenv("DIVERSITY_SIM_THRESHOLD", "0.85")),
    )


def scoring_env() -> dict:
    """스코어링/비용/임계값 관련 환경변수 로딩."""
    return dict(
        daily_budget_usd=float(os.getenv("DAILY_BUDGET_USD", "3.0")),
        peak_budget_multiplier=float(os.getenv("PEAK_BUDGET_MULTIPLIER", "0.5")),
        cost_alert_pct=float(os.getenv("COST_ALERT_PCT", "70")),
        heavy_categories=[
            c.strip()
            for c in os.getenv("HEAVY_CATEGORIES", "\uc815\uce58,\uacbd\uc81c,\ud14c\ud06c,\uc0ac\ud68c,\uad6d\uc81c,\uacfc\ud559,\uc0dd\ud65c,\ubc95\ub960").split(",")
            if c.strip()
        ],
        viral_score_llm_weight=float(os.getenv("VIRAL_SCORE_LLM_WEIGHT", "0.6")),
        min_cross_source_confidence=int(os.getenv("MIN_CROSS_SOURCE_CONFIDENCE", "2")),
        joongyeon_kick_long_form_threshold=int(os.getenv("JOONGYEON_KICK_LONG_FORM_THRESHOLD", "75")),
        jaccard_cluster_threshold=float(os.getenv("JACCARD_CLUSTER_THRESHOLD", "0.35")),
        embedding_cluster_threshold=float(os.getenv("EMBEDDING_CLUSTER_THRESHOLD", "0.75")),
        emerging_velocity_threshold=float(os.getenv("EMERGING_VELOCITY_THRESHOLD", "2.0")),
        emerging_volume_cap=int(os.getenv("EMERGING_VOLUME_CAP", "5000")),
        early_signal_boost_threshold=float(os.getenv("EARLY_SIGNAL_BOOST_THRESHOLD", "2.0")),
        early_signal_suppress_threshold=float(os.getenv("EARLY_SIGNAL_SUPPRESS_THRESHOLD", "0.3")),
        cache_ttl_rising=int(os.getenv("CACHE_TTL_RISING", "2")),
        cache_ttl_peak=int(os.getenv("CACHE_TTL_PEAK", "6")),
        cache_ttl_falling=int(os.getenv("CACHE_TTL_FALLING", "18")),
        cache_ttl_default=int(os.getenv("CACHE_TTL_DEFAULT", "12")),
        pattern_weight_min_samples=int(os.getenv("PATTERN_WEIGHT_MIN_SAMPLES", "3")),
        pattern_weight_days=int(os.getenv("PATTERN_WEIGHT_DAYS", "30")),
        genealogy_history_hours=int(os.getenv("GENEALOGY_HISTORY_HOURS", "72")),
        genealogy_min_confidence=float(os.getenv("GENEALOGY_MIN_CONFIDENCE", "0.5")),
        niche_bonus_points=int(os.getenv("NICHE_BONUS_POINTS", "10")),
    )


def platform_env() -> dict:
    """플랫폼/콘텐츠 관련 환경변수 로딩."""
    return dict(
        tone=os.getenv("TONE", "biojuho"),
        editorial_profile=os.getenv("EDITORIAL_PROFILE", "biojuho").lower(),
        target_languages=[lang.strip() for lang in os.getenv("TARGET_LANGUAGES", "ko").split(",") if lang.strip()],
        account_niche=os.getenv("ACCOUNT_NICHE", "bio/systems/content engineering/investing/saju"),
        target_audience=os.getenv("TARGET_AUDIENCE", "founders, researchers, operators, system thinkers"),
        enable_persona_filter=os.getenv("ENABLE_PERSONA_FILTER", "true").lower() == "true",
        persona_axes=[
            axis.strip()
            for axis in os.getenv("PERSONA_AXES", "bio,systems,content_engineering,investing,saju").split(",")
            if axis.strip()
        ],
        persona_min_matches=int(os.getenv("PERSONA_MIN_MATCHES", "1")),
        enforce_min_context_sources=os.getenv("ENFORCE_MIN_CONTEXT_SOURCES", "true").lower() == "true",
        min_context_sources=int(os.getenv("MIN_CONTEXT_SOURCES", "2")),
        enforce_source_diversity_gate=os.getenv("ENFORCE_SOURCE_DIVERSITY_GATE", "true").lower() == "true",
        required_source_combinations=[
            combo.strip()
            for combo in os.getenv(
                "REQUIRED_SOURCE_COMBINATIONS",
                "twitter+news,reddit+news,twitter+reddit",
            ).split(",")
            if combo.strip()
        ],
        enforce_hard_drop_policy=os.getenv("ENFORCE_HARD_DROP_POLICY", "true").lower() == "true",
        hard_drop_topic_keywords=[
            keyword.strip()
            for keyword in os.getenv(
                "HARD_DROP_TOPIC_KEYWORDS",
                "fursuit,fursuitfriday,cosplay,lol,league of legends,viego,patch notes,buff,nerf,hair trend,haircut,beauty trend,fashion trend,meme,shitpost",
            ).split(",")
            if keyword.strip()
        ],
        target_platforms=[p.strip() for p in os.getenv("TARGET_PLATFORMS", "x").split(",") if p.strip()],
        content_hub_database_id=os.getenv("CONTENT_HUB_DATABASE_ID", ""),
        blog_min_score=int(os.getenv("BLOG_MIN_SCORE", "70")),
        blog_min_words=int(os.getenv("BLOG_MIN_WORDS", "2000")),
        blog_max_words=int(os.getenv("BLOG_MAX_WORDS", "5000")),
        blog_seo_keywords_count=int(os.getenv("BLOG_SEO_KEYWORDS_COUNT", "5")),
        news_rss_max_items=int(os.getenv("NEWS_RSS_MAX_ITEMS", "5")),
        exclude_categories=[
            c.strip() for c in os.getenv("EXCLUDE_CATEGORIES", "\uc815\uce58,\uc5f0\uc608").split(",") if c.strip()
        ],
        niche_categories=[c.strip() for c in os.getenv("NICHE_CATEGORIES", "AI,\ud14c\ud06c").split(",") if c.strip()],
        watchlist_keywords=[k.strip() for k in os.getenv("WATCHLIST_KEYWORDS", "").split(",") if k.strip()],
        content_diversity_hours=int(os.getenv("CONTENT_DIVERSITY_HOURS", "24")),
        generation_mode_override=os.getenv("GENERATION_MODE", ""),
        persona_rotation=os.getenv("PERSONA_ROTATION", "fixed"),
        persona_pool=[
            p.strip() for p in os.getenv("PERSONA_POOL", "biojuho").split(",") if p.strip()
        ],
    )
