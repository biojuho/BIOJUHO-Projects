"""
getdaytrends v4.1 - Configuration Management
????듬젿?怨뚮뼚????棺??짆?삠궘? ??れ삀???筌? ???レ챺????濡ろ떟???? 濚욌꼬?댄꺍?????굿??
"""

import os
from dataclasses import dataclass, field
from functools import cached_property

try:
    from shared.env_loader import load_workspace_env
    load_workspace_env()
except ImportError:
    from dotenv import load_dotenv
    load_dotenv()

VERSION = "4.1"


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

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


@dataclass(frozen=True)
class QualityConfig:
    """???源녿뼥 ???굿?????源놁젳????ш끽維곮????"""
    feedback_min_score: int = 50
    threads_quality_min_score: int = 65
    long_form_quality_min_score: int = 70
    blog_quality_min_score: int = 75
    fact_check_min_accuracy: float = 0.6
    fact_check_strict_mode: bool = False
    hallucination_zero_tolerance: bool = True
    enable_quality_feedback: bool = True
    enable_golden_reference_qa: bool = True
    golden_reference_limit: int = 3
    min_viral_score: int = 60


@dataclass(frozen=True)
class CostConfig:
    """????????굿?????源놁젳????ш끽維곮????"""
    daily_budget_usd: float = 3.0
    peak_budget_multiplier: float = 0.5
    cost_alert_pct: float = 70.0
    heavy_categories: tuple[str, ...] = ("\uC815\uCE58", "\uACBD\uC81C", "\uD14C\uD06C", "\uC0AC\uD68C", "\uAD6D\uC81C", "\uACFC\uD559", "\uC0DD\uD65C", "\uBC95\uB960")
    qa_skip_cached: bool = True
    qa_skip_high_score: int = 85
    qa_skip_categories: tuple[str, ...] = ("\uC720\uBA38", "\uD478\uB4DC", "\uC2A4\uD3EC\uCE20")
    generation_mode_override: str = ""


@dataclass(frozen=True)
class AlertConfig:
    """?????癲???紐????源놁젳????ш끽維곮????"""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    slack_webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_email: str = ""
    alert_threshold: int = 70

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def has_discord(self) -> bool:
        return bool(self.discord_webhook_url)

    @property
    def has_any_channel(self) -> bool:
        return self.has_telegram or self.has_discord or bool(self.slack_webhook_url)


@dataclass
class AppConfig:
    # LLM?? shared.llm 癲ル슢?꾤땟??????????굿??(??룸Ŧ爾??.env????????棺??짆?승?

    # Storage: Notion
    notion_token: str = ""
    notion_database_id: str = ""

    # Storage: Google Sheets
    google_service_json: str = "credentials.json"
    google_sheet_id: str = ""

    # Storage type: "notion", "google_sheets", "both", "none"
    storage_type: str = "notion"

    # Storage: Database
    # SQLite ??れ삀??? PostgreSQL ??ш낄援?? DATABASE_URL=postgresql://user:pw@host/db
    db_path: str = "data/getdaytrends.db"
    database_url: str = ""  # ???源놁젳 ??PostgreSQL ????(SQLite ???뺤깓??

    # Schedule
    schedule_minutes: int = 360
    enable_parallel_countries: bool = True
    country_parallel_limit: int = 3

    # Tone
    tone: str = "\uCE5C\uADFC\uD558\uACE0 \uC704\uD2B8 \uC788\uB294 \uB3D9\uB124 \uCE5C\uAD6C"
    editorial_profile: str = "report"  # ?潁뺛깺猷?Threads/??怨?繞벿삳쎖??쇱춻熬곣뫖裕??嶺뚮ㅎ?당빊???ш끽維곩ㅇ??

    # Multi-source API keys
    twitter_bearer_token: str = ""
    # X OAuth 2.0 (??????怨룸츛): PKCE ???鸚???ㅻ깹鸚??袁⑸즵獒?????? ????녿룵?????ャ뀕??
    x_access_token: str = ""  # ?嶺뚮ㅎ?댐쭕??濡ろ뜐????OAuth 2.0 Bearer
    x_client_id: str = ""  # X Developer App Client ID
    x_client_secret: str = ""  # X Developer App Client Secret

    # Twikit (??????X ???????⑤９苑??????熬곣뱿逾???ш끽維???????
    twikit_username: str = ""  # ??ш끽維??X ??節뚮쳮??????????
    twikit_email: str = ""  # ??ш끽維??X ??節뚮쳮?????嶺??
    twikit_password: str = ""  # ??ш끽維??X ??節뚮쳮???????類????

    # Alerts
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    slack_webhook_url: str = ""  # [C-5] Slack Incoming Webhook URL
    smtp_host: str = ""  # [C-5] SMTP ??筌먦끉裕??嶺뚮ㅎ?ц짆??
    smtp_port: int = 587  # [C-5] SMTP ????(587=STARTTLS, 465=SSL)
    smtp_user: str = ""  # [C-5] SMTP ?嶺뚮ㅎ?댐ℓ??????
    smtp_password: str = ""  # [C-5] SMTP ?嶺뚮ㅎ?댐ℓ??????類????
    alert_email: str = ""  # [C-5] ???????筌뚯슜堉????嶺????낆뒩???
    alert_threshold: int = 70

    # v2.4 ??れ삀????????μ쐺?
    enable_clustering: bool = True
    enable_long_form: bool = True
    enable_threads: bool = True
    smart_schedule: bool = True
    night_mode: bool = True
    long_form_min_score: int = 95  # ???⑤?彛쒙┼??潁뺛깺猷???獄쏅똻??(Sonnet ?????????ル춪) [C1: 90??5]
    thread_min_score: int = 999  # ???ㅻ깹????????濚밸Ŧ遊??(?????????ル춪)
    threads_min_score: int = 65  # ???⑤?彛쒙┼?Meta Threads ??獄쏅똻??
    min_viral_score: int = 60  # ???源녿뼥 ??ш낄援?? 雅?퍔瑗띰㎖?뱁맪??????熬곣뫕????????獄쏅똻??癲꾧퀗????? [??れ삀???55 ??60]
    max_workers: int = 10  # ????덈빰 HTTP ??釉먯뒜????[??れ삀???6 ??10]
    daily_budget_usd: float = 3.0  # ???????????ㅺ강??($). ?縕?????Sonnet ???筌??????濚밸Ŧ遊??[v13.0: $2??3]
    # ?怨멸텭??沃섅뀙??關履?????LLM ???Β?ш퐨 ??繹먮끏裕?? ??????怨멸텭??沃섅뀙??關履??⑥궡異?Sonnet(HEAVY) ???? ??嚥?猷ワ┼??넊???Haiku
    heavy_categories: list = field(
        default_factory=lambda: ["\uC815\uCE58", "\uACBD\uC81C", "\uD14C\uD06C", "\uC0AC\uD68C", "\uAD6D\uC81C", "\uACFC\uD559", "\uC0DD\uD65C", "\uBC95\uB960"]
    )
    # [C2] ??癰???????????? ????ㅒ????癰??????館??????숇젿) ???????????(1.0=????곕럡, 0.5=????고떘)
    peak_budget_multiplier: float = 0.5  # off-peak(22~07?? ??????= daily * 0.5
    cost_alert_pct: float = 70.0  # ??繹먮끏?????????70% ??ш끽維?????濡ろ뜑???

    # ===================================================
    # [v2.5] High-Quality / Transcreation
    # ===================================================
    target_languages: list[str] = field(default_factory=lambda: ["ko"])  # ?嶺뚮ㅎ?????袁⑹뵫?域밸Ŧ遊????⑤젰???????嶺뚮ㅎ???

    # Canva API Integration
    canva_api_key: str = ""
    canva_client_id: str = ""
    canva_client_secret: str = ""
    canva_template_id: str = ""
    enable_canva_visuals: bool = False  # [C-4] ??關履???????嶺뚮ㅎ????????뱀낄?????筌???獄쏅똻??
    canva_min_score: int = 90  # [C-4] ??????????⑤?彛?????????뱀낄????獄쏅똻??

    # ===================================================
    # [v3.0] ???源녿뼥勇싲８???筌믨퀣???釉띾엮塋???ш낄援??
    # ===================================================
    # Phase 1: ???ル굔??
    cache_volume_bucket: int = 5000  # ???쒋???ш끽諭욥???怨뚮옩????類???앹쒜?????(????獄??嚥?흮 ?嶺?)
    data_retention_days: int = 90  # DB ???Β?????怨뚮옖?????れ삀??㉱?(??
    notion_sem_limit: int = 10  # Notion ????덈빰 ????癲ル슔?됭짆? ?嶺뚮ㅎ?붺빊??????

    # Phase 3: ???굿癲???좊읈????묐빝?
    enable_structured_metrics: bool = True  # ??????ш끽維곲????ш끽維????JSON ????깼???癲ル슢????용끏???棺??짆??

    # Phase 4: ??關履???
    enable_sentiment_filter: bool = True  # ???ャ뀖???嶺뚮ㅎ???????筌???ш낄援??(safety_flag=True ???袁⑤툞)

    # ===================================================
    # [v4.0] ?嶺뚮ㅎ?????濡ろ떟?癲?& ???쒓낮???怨쀫뮛???????몄????鶯?
    # ===================================================
    # Phase 1: 癲ル슢議????Β?ろ떖???????뤆??濡ろ떟?癲?
    min_cross_source_confidence: int = 2  # ???????0~4) 雅?퍔瑗띰㎖?뱁맪?????viral_potential 65% ???釉먭숱??
    # Phase 2: ???쒓낮???怨쀫뮛???????몄????鶯???좊읈?濚욌꼬?댄꺍??
    viral_score_llm_weight: float = 0.6  # LLM ?????????룔뀋?(??嚥?猷ワ┼??넊?????癰궽쇱읇???????
    # Phase 3: ???怨뺤릇???ル깼????????怨뚮옖???
    enable_history_correction: bool = True  # ?袁⑸즵??????嚥????嶺뚮ㅎ???????筌???????怨뚮옖???
    # Phase 4: 濚욌꼬?댄꺍?????????
    joongyeon_kick_long_form_threshold: int = 75  # ???⑤?彛??????潁뺛깺猷?min_score ???μ쪠????獄쏅똻??

    # ===================================================
    # [v5.0] ???獒????源녿뼥 ???⑤벚???+ YouTube
    # ===================================================
    enable_source_quality_tracking: bool = True  # ???獒????源녿뼥 DB ??れ삀??쎈뭄???筌????
    news_rss_max_items: int = 5  # Google News RSS 癲ル슔?됭짆? ???쒓낯????

    # ===================================================
    # [v6.0] ???源녿뼥 ???⑤벚?????룸Ŧ爾??+ ?怨멸텭??沃섅뀙??關履?????怨좊젳??
    # ===================================================
    min_article_count: int = 3  # ??????ш끽維곲??癲ル슔?됭짆????れ삀?節놁쒜????怨뚮옖???[v13.0: 5??, ?????源녿뼥 ??좊즴甕??????袁⑸젻泳?]
    max_same_category: int = 2  # ????곕럡 ?怨멸텭??沃섅뀙??關履??癲ル슔?됭짆? ??れ삀?節놁쒜???
    enable_quality_feedback: bool = True  # ??獄쏅똻????LLM ???源녿뼥 ?濡ろ떟?癲???筌????
    quality_feedback_min_score: int = 50  # QA ???????雅?퍔瑗띰㎖?뱁맪???????濚??
    threads_quality_min_score: int = 65  # Threads QA 癲ル슔?됭짆???????
    long_form_quality_min_score: int = 70  # X ?潁뺛깺猷?QA 癲ル슔?됭짆???????
    blog_quality_min_score: int = 75  # ???源낇꼧????怨?繞벿삳쎖??QA 癲ル슔?됭짆???????

    # ===================================================
    # [v6.1] 癲ル슔?됭짆????濡ろ떟?癲?(Freshness Validation)
    # ===================================================
    max_content_age_hours: int = 24  # ????癰????縕????嶺뚮ㅎ????筌먲퐢痢?expired ?濚밸Þ???
    freshness_penalty_stale: float = 0.85  # stale (6~12h) ???釉먭숱???袁⑸즲???
    freshness_penalty_expired: float = 0.7  # expired (12h+) ???釉먭숱???袁⑸즲???

    # ===================================================
    # [v7.0] ?怨멸텭??沃섅뀙??關履????筌믨퀡????ш낄援??
    # ===================================================
    exclude_categories: list[str] = field(
        default_factory=lambda: ["\uC815\uCE58", "\uC5F0\uC608"]
    )  # ???怨멸텭??沃섅뀙??關履????嶺뚮ㅎ????? ??????ш끽維곲?嶺뚮ㅎ???????筌???筌믨퀡??

    # ===================================================
    # [v8.0] ??節뚮쳮???嶺뚮Ĳ????(??ш끽維???ш낄援θキ??? 癲ル슢?섊몭???????????爾?????덉쉐)
    # ===================================================
    account_niche: str = "AI/\uD14C\uD06C/\uD2B8\uB80C\uB4DC"  # account niche
    target_audience: str = "IT \uC885\uC0AC\uC790, \uC2A4\uD0C0\uD2B8\uC5C5 \uAD00\uACC4\uC790"  # target audience

    # ===================================================
    # [v9.0] Phase A: ?????癲ル슔?됭짆???
    # ===================================================
    jaccard_cluster_threshold: float = 0.35  # ?棺??짆?쏆춾????????袁⑸뙃癲????モ?????ш낄猷?嚥♂쇱씀?
    # [v14.0] Gemini Embedding 2 ????????????袁⑸뙃癲?
    enable_embedding_clustering: bool = True  # True=Gemini Embedding ??れ삀??뫢?????????モ???(Jaccard ???筌??????
    embedding_cluster_threshold: float = 0.75  # ?熬곣뫀毓쇌벧?????モ?????ш낄猷?嚥♂쇱씀?(0.0~1.0, ?亦껋꼨援?キ??嚥?흮 ??ш낄猷볣걡?
    qa_skip_cached: bool = True  # 癲??????雅???熬곣뫕??????QA ???袁⑤툞
    qa_skip_high_score: int = 85  # ??????????⑤?彛??嶺뚮ㅎ????QA ???袁⑤툞
    qa_skip_categories: list[str] = field(default_factory=lambda: ["\uB0A0\uC528", "\uC74C\uC2DD", "\uC2A4\uD3EC\uCE20"])
    generation_mode_override: str = ""  # "" = auto | "full" = ?潁뺛깺猷?????| "lite" = ????壤?

    # ===================================================
    # [v10.0] Phase 1: ???爾?????덉쉐 ??좊즴甕??
    # ===================================================
    require_context: bool = True  # True=???爾?????덉쉐 ???⑤챶?뺧┼???獄쏅똻??????(??ш끽維???
    cache_ttl_rising: int = 2  # ???ㅼ굡獄?옋夷??嶺뚮ㅎ????癲????TTL (??癰???
    cache_ttl_peak: int = 6  # ?嶺뚮Ĳ????嶺뚮ㅎ????癲????TTL (??癰???
    cache_ttl_falling: int = 18  # ??嚥??끿튊??嶺뚮ㅎ????癲????TTL (??癰???
    cache_ttl_default: int = 12  # 雅?퍔瑗띰㎖??誘⒲걫?癲????TTL (??癰???

    # ===================================================
    # [v9.0] Phase B: ???源녿뼥 癲ル슔?됭짆???
    # ===================================================
    watchlist_keywords: list[str] = field(default_factory=list)  # ???굿?????源낆맫??(???硫κ괴 ????㎦??
    enable_content_diversity: bool = True  # ???⑤챷????獄쏅똻??????猿????ш끽維???ш낄援θキ????낆뒩????濚욌꼬?댄꺇???袁⑸젻泳?
    content_diversity_hours: int = 24  # ???⑤챷???嶺뚮ㅎ?댐쭕??釉뚰????類????(??癰???
    enable_velocity_scoring: bool = True  # ?怨뚮옩??????ㅼ굡獄?????뽦뵣 癲ル슣???????レ챺繹???????袁⑸즵???

    # ===================================================
    # [v9.0] Phase C: ?????????嶺뚮ㅎ????????
    # ===================================================
    enable_emerging_detection: bool = True  # ???怨뚮옩?????關履?怨쀫눛??筌?六????????????좊즴?? ??筌????
    emerging_velocity_threshold: float = 2.0  # ???袁⑸즲??????⑤?彛???????????????ш끽維亦?
    emerging_volume_cap: int = 5000  # ???怨뚮옩?????熬곣뫀?껓┼???????????ш끽維亦?

    # ===================================================
    # [v12.0] 癲ル슢議????μ쪚????鸚??熬곣뫕?????????⑤㈇猿
    # ===================================================
    target_platforms: list[str] = field(
        default_factory=lambda: ["x", "threads"]
    )  # [v13.0] naver_blog ??癰귙끋源?(X/Threads癲?
    enable_content_hub: bool = False  # Content Hub second Notion DB write
    content_hub_database_id: str = ""  # 癲ル슢議????μ쪚????鸚?Content Hub ?嶺뚮ㅎ???DB ID
    blog_min_score: int = 70  # ??????????⑤?彛쒙┼????源낇꼧????怨?繞벿삳쎖????れ꽔?????獄쏅똻??
    blog_min_words: int = 2000  # ???源낇꼧????怨?繞벿삳쎖??癲ル슔?됭짆????れ꽔?????
    blog_max_words: int = 5000  # ???源낇꼧????怨?繞벿삳쎖??癲ル슔?됭짆? ??れ꽔?????
    blog_seo_keywords_count: int = 5  # SEO ???源낆맫????⑤베毓????

    # ===================================================
    # [v15.0] Phase A: Zero Content Prevention + Niche Scoring
    # ===================================================
    enable_zero_content_prevention: bool = True  # 癲ル슢?꾤땟????嶺뚮ㅎ????? ??筌믨퀡???怨멸텭??沃섅뀙??關履?????癲ル슔?됭짆??1???怨뚮옖???
    niche_categories: list[str] = field(default_factory=lambda: ["AI", "\uD14C\uD06C"])  # niche bonus targets
    niche_bonus_points: int = 10  # ????萸??怨멸텭??沃섅뀙??關履???怨뚮옖?????????
    enable_lazy_context: bool = True  # 癲ル슣???????爾?????덉쉐 ?棺??짆?승???筌????

    # ===================================================
    # [v15.0] Phase B: Content Diversity + Persona Rotation
    # ===================================================
    diversity_sim_threshold: float = 0.85  # ?熬곣뫕?????????モ?????ш낄猷?嚥♂쇱씀?(???⑤?彛?????濚욌꼬?댄꺇???????
    persona_rotation: str = "category"  # ??繹먮굛??????ャ뀕??癲ル슢?꾤땟??? category | round_robin | fixed
    persona_pool: list[str] = field(default_factory=lambda: ["joongyeon", "analyst", "storyteller"])

    # ===================================================
    # [v5.0] B. Adaptive Voice ???濚밸Þ?볠쾮???れ삀??뫢????????좊읈?濚욌꼬?댄꺍??
    # ===================================================
    enable_adaptive_voice: bool = True  # ?????????딆녃??濚밸Þ?볠쾮???좊읈?濚욌꼬?댄꺍????ш끽維???ш낄援θキ???낆뒩???
    pattern_weight_min_samples: int = 3  # ??좊읈?濚욌꼬?댄꺍????節뚮쳮雅?癲ル슔?됭짆?????얜?源???
    pattern_weight_days: int = 30  # ??좊읈?濚욌꼬?댄꺍????節뚮쳮雅???れ삀??㉱?(??

    # ===================================================
    # [v5.0] D. Real-time Signal ??3??影?됀????쒓낯??
    # ===================================================
    enable_tiered_collection: bool = True  # 3??影?됀????쒓낯????筌????(1h/6h/48h)
    early_signal_boost_threshold: float = 2.0  # ?縕?猿녿뎨?ER????????N?????⑤?彛???????ш끽維뽫댆??熬곣뫕???????嶺뚮ㅎ遊뉔걡酉멥??
    early_signal_suppress_threshold: float = 0.3  # ?縕?猿녿뎨?ER????????N????熬곣뫀????????? ??좊읈?濚욌꼬?댄꺍?????얜Ŋ源?

    # ===================================================
    # [v5.0] E. Benchmark QA ????貫???????녿군???Β?レ릇
    # ===================================================
    enable_golden_reference_qa: bool = True  # ??貫???????녿군???Β?レ릇 ??れ삀??뫢????????? QA
    golden_reference_limit: int = 3  # QA ??ш끽維???ш낄援θキ????낆뒩????????녿군???Β?レ릇 ??
    golden_reference_auto_update_days: int = 7  # ???筌???좊즲????釉뚰?????れ삀??㉱?(??

    # ===================================================
    # [v5.0] A. Trend Genealogy ???嶺뚮ㅎ??????節뚮쳥????됰슣維??
    # ===================================================
    enable_trend_genealogy: bool = True  # ?嶺뚮ㅎ??????節뚮쳥????됰슣維????筌????
    genealogy_history_hours: int = 72  # ??節뚮쳥?????怨뺤릇???ル깼???釉뚰?????れ삀??㉱?(??癰???
    genealogy_min_confidence: float = 0.5  # ??節뚮쳥?????ㅼ뒦??癲ル슔?됭짆???嶺뚮Ĳ?뉛쭛??

    # ===================================================
    # [v6.0] ?嶺뚮㉡?€쾮??嶺뚮쮳?곌섈???濡ろ떟?癲?
    # ===================================================
    enable_fact_checking: bool = True  # ??獄쏅똻???熬곣뫕?????????됰씭肄?癲ル슪???띿물???筌????
    fact_check_min_accuracy: float = 0.6  # ???됰씭肄?癲ル슪???띿물?癲ル슔?됭짆???嶺뚮쮳?곌섈??(0~1, 雅?퍔瑗띰㎖?뱁맪???????濚??
    fact_check_strict_mode: bool = False  # True癲??嶺뚮ㅎ???????????ш낄猷볣걡??濡ろ떟?癲?
    enable_source_credibility: bool = True  # ??⑥レ툔?????ル굔????좊읈?濚욌꼬?댄꺍?????ㅼ굣??
    credibility_penalty_threshold: float = 0.3  # ?????ル굔??雅?퍔瑗띰㎖?뱁맪?????viral_potential ???釉먭숱??
    credibility_penalty_factor: float = 0.85  # ?????ル굔???⑥レ툔?????釉먭숱???袁⑸즲???
    enable_cross_source_consistency: bool = True  # ???獒?????????濡ろ떟?癲???筌????
    hallucination_zero_tolerance: bool = True  # True癲?????깅쐺 ??좊즴?? ?????뺤깓??濡????濚??

    # ===================================================
    # [v16.0] EDAPE ??Engagement-Driven Adaptive Prompt Engine
    # ===================================================
    enable_edape: bool = True  # EDAPE ???ㅼ굣甕????ш끽維???ш낄援θキ???釉먯뒭????筌????
    edape_lookback_days: int = 7  # ?濚밸Þ?볠쾮????Β?????釉뚰?????れ삀??㉱?(??
    edape_max_suppression_ratio: float = 0.3  # ???쒓낮彛???????????癲ル슔?됭짆? ?????

    # ===================================================
    # [v16.0] TAP ??Trend Arbitrage Publisher
    # ===================================================
    enable_tap: bool = True  # ?????뤆?끚곻쭔?? ?嶺뚮ㅎ????癲ル슓堉곁땟???깊??ㅻ깹????좊즴?? ??筌????
    tap_lookback_hours: int = 12  # 癲ル슓堉곁땟???깊??ㅻ깹????좊즴?? ?釉뚰?????れ삀??㉱?(??癰???
    tap_min_viral_score: int = 60  # 癲ル슓堉곁땟???깊??ㅻ깹????좊즴?? 癲ル슔?됭짆???袁⑸즴????????몄???

    # ===================================================
    # [v16.0] Streaming Pipeline ??Event-Driven ????덉쉐?域밸Ŧ留⑶뜮?
    # ===================================================
    enable_streaming_pipeline: bool = False  # asyncio.Queue ????덉쉐?域밸Ŧ留⑶뜮?癲ル슢?꾤땟?????筌????(????딅쾷??
    streaming_generator_concurrency: int = 3  # ????덉쉐?域밸Ŧ留⑶뜮?癲ル슢?꾤땟???????덈빰 LLM ?嶺뚮ㅎ?????
    streaming_stage_timeout: int = 120  # ???쒒?????읐??? ????ш끽維???(??

    tap_snapshot_max_age_minutes: int = 30
    tap_board_limit: int = 10
    tap_teaser_count: int = 3
    enable_tap_alert_queue: bool = True
    tap_alert_top_k: int = 3
    tap_alert_min_priority: float = 80.0
    tap_alert_min_viral_score: int = 75
    tap_alert_cooldown_minutes: int = 180
    enable_tap_alert_dispatch: bool = False
    tap_alert_dispatch_batch_size: int = 5
    # Runtime options (CLI overrides)
    country: str = "korea"
    countries: list = field(default_factory=list)
    limit: int = 10
    dedupe_window_hours: int = 6
    one_shot: bool = False
    dry_run: bool = False
    verbose: bool = False
    no_alerts: bool = False

    def __post_init__(self):
        if not self.countries:
            self.countries = [self.country]

    # [QA ???쒓낯?? @property ??@cached_property: 癲??嶺뚮ㅎ?????좊즵??꼯????獄쏅똻???袁⑸젻泳?
    @cached_property
    def quality(self) -> QualityConfig:
        """???源녿뼥 ???굿?????源놁젳 ??ш끽維곮????(cached)."""
        return QualityConfig(
            feedback_min_score=self.quality_feedback_min_score,
            threads_quality_min_score=self.threads_quality_min_score,
            long_form_quality_min_score=self.long_form_quality_min_score,
            blog_quality_min_score=self.blog_quality_min_score,
            fact_check_min_accuracy=self.fact_check_min_accuracy,
            fact_check_strict_mode=self.fact_check_strict_mode,
            hallucination_zero_tolerance=self.hallucination_zero_tolerance,
            enable_quality_feedback=self.enable_quality_feedback,
            enable_golden_reference_qa=self.enable_golden_reference_qa,
            golden_reference_limit=self.golden_reference_limit,
            min_viral_score=self.min_viral_score,
        )

    @cached_property
    def cost(self) -> CostConfig:
        """????????굿?????源놁젳 ??ш끽維곮????(cached)."""
        return CostConfig(
            daily_budget_usd=self.daily_budget_usd,
            peak_budget_multiplier=self.peak_budget_multiplier,
            cost_alert_pct=self.cost_alert_pct,
            heavy_categories=tuple(self.heavy_categories),
            qa_skip_cached=self.qa_skip_cached,
            qa_skip_high_score=self.qa_skip_high_score,
            qa_skip_categories=tuple(self.qa_skip_categories),
            generation_mode_override=self.generation_mode_override,
        )

    @cached_property
    def alerts(self) -> AlertConfig:
        """?????癲???紐????源놁젳 ??ш끽維곮????(cached)."""
        return AlertConfig(
            telegram_bot_token=self.telegram_bot_token,
            telegram_chat_id=self.telegram_chat_id,
            discord_webhook_url=self.discord_webhook_url,
            slack_webhook_url=self.slack_webhook_url,
            smtp_host=self.smtp_host,
            smtp_port=self.smtp_port,
            smtp_user=self.smtp_user,
            smtp_password=self.smtp_password,
            alert_email=self.alert_email,
            alert_threshold=self.alert_threshold,
        )

    @staticmethod
    def _storage_env() -> dict:
        """Storage ???굿??????듬젿?怨뚮뼚????棺??짆?승?"""
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

    @staticmethod
    def _schedule_env() -> dict:
        """???濚욌꼬釉먮뮎?猷몄굣????????굿??????듬젿?怨뚮뼚????棺??짆?승?"""
        return dict(
            schedule_minutes=int(os.getenv("SCHEDULE_INTERVAL_MINUTES", "360")),
            enable_parallel_countries=os.getenv("ENABLE_PARALLEL_COUNTRIES", "true").lower() == "true",
            country_parallel_limit=int(os.getenv("COUNTRY_PARALLEL_LIMIT", "3")),
            country=os.getenv("DEFAULT_COUNTRY", "korea"),
            limit=int(os.getenv("DEFAULT_LIMIT", "10")),
            dedupe_window_hours=int(os.getenv("DEDUPE_WINDOW_HOURS", "6")),
            max_workers=int(os.getenv("MAX_WORKERS", "10")),
        )

    @staticmethod
    def _api_keys_env() -> dict:
        """?嶺? API ??沃섃뫜?????????굿??????듬젿?怨뚮뼚????棺??짆?승?"""
        return dict(
            twitter_bearer_token=os.getenv("TWITTER_BEARER_TOKEN", ""),
            x_access_token=os.getenv("X_ACCESS_TOKEN", ""),
            x_client_id=os.getenv("X_CLIENT_ID", ""),
            x_client_secret=os.getenv("X_CLIENT_SECRET", ""),
            twikit_username=os.getenv("TWIKIT_USERNAME", ""),
            twikit_email=os.getenv("TWIKIT_EMAIL", ""),
            twikit_password=os.getenv("TWIKIT_PASSWORD", ""),
            canva_api_key=os.getenv("CANVA_API_KEY", ""),
            canva_client_id=os.getenv("CANVA_CLIENT_ID", ""),
            canva_client_secret=os.getenv("CANVA_CLIENT_SECRET", ""),
            canva_template_id=os.getenv("CANVA_TEMPLATE_ID", ""),
        )

    @staticmethod
    def _alerts_env() -> dict:
        """?????癲???紐????굿??????듬젿?怨뚮뼚????棺??짆?승?"""
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

    @staticmethod
    def _feature_flags_env() -> dict:
        """??れ삀????????μ쐺?????듬젿?怨뚮뼚????棺??짆?승?"""
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

    @staticmethod
    def _quality_env() -> dict:
        """???源녿뼥勇싲８?딞 ???굿??????듬젿?怨뚮뼚????棺??짆?승?"""
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
                c.strip() for c in os.getenv("QA_SKIP_CATEGORIES", "\uB0A0\uC528,\uC74C\uC2DD,\uC2A4\uD3EC\uCE20").split(",") if c.strip()
            ],
            golden_reference_limit=int(os.getenv("GOLDEN_REFERENCE_LIMIT", "3")),
            golden_reference_auto_update_days=int(os.getenv("GOLDEN_REFERENCE_AUTO_UPDATE_DAYS", "7")),
            diversity_sim_threshold=float(os.getenv("DIVERSITY_SIM_THRESHOLD", "0.85")),
        )

    @staticmethod
    def _scoring_env() -> dict:
        """????몄????鶯ㅼ룆援욄??癰궽쇱읇?????굿??????듬젿?怨뚮뼚????棺??짆?승?"""
        return dict(
            daily_budget_usd=float(os.getenv("DAILY_BUDGET_USD", "3.0")),
            peak_budget_multiplier=float(os.getenv("PEAK_BUDGET_MULTIPLIER", "0.5")),
            cost_alert_pct=float(os.getenv("COST_ALERT_PCT", "70")),
            heavy_categories=[
                c.strip()
                for c in os.getenv("HEAVY_CATEGORIES", "\uC815\uCE58,\uACBD\uC81C,\uD14C\uD06C,\uC0AC\uD68C,\uAD6D\uC81C,\uACFC\uD559,\uC0DD\uD65C,\uBC95\uB960").split(",")
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

    @staticmethod
    def _platform_env() -> dict:
        """?????????룑?????????굿??????듬젿?怨뚮뼚????棺??짆?승?"""
        return dict(
            tone=os.getenv("TONE", "\uCE5C\uADFC\uD558\uACE0 \uC704\uD2B8 \uC788\uB294 \uB3D9\uB124 \uCE5C\uAD6C"),
            editorial_profile=os.getenv("EDITORIAL_PROFILE", "report").lower(),
            target_languages=[lang.strip() for lang in os.getenv("TARGET_LANGUAGES", "ko").split(",") if lang.strip()],
            account_niche=os.getenv("ACCOUNT_NICHE", "AI/\uD14C\uD06C/\uD2B8\uB80C\uB4DC"),
            target_audience=os.getenv("TARGET_AUDIENCE", "IT \uC885\uC0AC\uC790, \uC2A4\uD0C0\uD2B8\uC5C5 \uAD00\uACC4\uC790"),
            target_platforms=[p.strip() for p in os.getenv("TARGET_PLATFORMS", "x").split(",") if p.strip()],
            content_hub_database_id=os.getenv("CONTENT_HUB_DATABASE_ID", ""),
            blog_min_score=int(os.getenv("BLOG_MIN_SCORE", "70")),
            blog_min_words=int(os.getenv("BLOG_MIN_WORDS", "2000")),
            blog_max_words=int(os.getenv("BLOG_MAX_WORDS", "5000")),
            blog_seo_keywords_count=int(os.getenv("BLOG_SEO_KEYWORDS_COUNT", "5")),
            news_rss_max_items=int(os.getenv("NEWS_RSS_MAX_ITEMS", "5")),
            exclude_categories=[
                c.strip() for c in os.getenv("EXCLUDE_CATEGORIES", "\uC815\uCE58,\uC5F0\uC608").split(",") if c.strip()
            ],
            niche_categories=[c.strip() for c in os.getenv("NICHE_CATEGORIES", "AI,\uD14C\uD06C").split(",") if c.strip()],
            watchlist_keywords=[k.strip() for k in os.getenv("WATCHLIST_KEYWORDS", "").split(",") if k.strip()],
            content_diversity_hours=int(os.getenv("CONTENT_DIVERSITY_HOURS", "24")),
            generation_mode_override=os.getenv("GENERATION_MODE", ""),
            persona_rotation=os.getenv("PERSONA_ROTATION", "category"),
            persona_pool=[
                p.strip() for p in os.getenv("PERSONA_POOL", "joongyeon,analyst,storyteller").split(",") if p.strip()
            ],
        )

    @classmethod
    def from_env(cls) -> "AppConfig":
        """????듬젿?怨뚮뼚???筌뚯슧諭?????源놁젳 ?棺??짆?승? ?怨멸텭??沃섅뀙??關履?????????癲ル슢??袁λ빝??筌먦끉큔 ??됰슣維??"""
        kwargs: dict = {}
        kwargs.update(cls._storage_env())
        kwargs.update(cls._schedule_env())
        kwargs.update(cls._api_keys_env())
        kwargs.update(cls._alerts_env())
        kwargs.update(cls._feature_flags_env())
        kwargs.update(cls._quality_env())
        kwargs.update(cls._scoring_env())
        kwargs.update(cls._platform_env())
        return cls(**kwargs)

    def validate(self) -> list[str]:
        """????곸씔 癲ル슢?꾤땟戮⑤뭄??袁⑸즵??? ???域밸Ŧ遊얕짆?嶺뚮ㅎ?닻얠쥉異????レ챺??"""
        from shared.llm.config import load_keys

        errors = []
        keys = load_keys()
        if not any(keys.values()):
            errors.append("LLM API ??? ???源놁젳??? ????⒱봼??????(??룸Ŧ爾??.env ?嶺뚮Ĳ?됮?.")

        if self.storage_type in ("notion", "both"):
            if not self.notion_token or "your_" in self.notion_token:
                errors.append("NOTION_TOKEN?????源놁젳??? ????⒱봼??????")
            if not self.notion_database_id or "your_" in self.notion_database_id:
                errors.append("NOTION_DATABASE_ID??좊읈? ???源놁젳??? ????⒱봼??????")

        if self.storage_type in ("google_sheets", "both"):
            if not self.google_sheet_id or "your_" in self.google_sheet_id:
                errors.append("GOOGLE_SHEET_ID??좊읈? ???源놁젳??? ????⒱봼??????")
            if not os.path.exists(self.google_service_json):
                errors.append(f"Google ??筌먐삳４????節뚮쳮??JSON??癲ル슓??젆???????⑤８?????덊렡: {self.google_service_json}")

        if self.enable_content_hub and not self.content_hub_database_id:
            errors.append("ENABLE_CONTENT_HUB=true ???癲?CONTENT_HUB_DATABASE_ID??좊읈? ????룹젂????怨?????덊렡.")

        # ???쒓랜萸??類?????濡ろ떟?癲?
        valid_storage = {"notion", "google_sheets", "both", "none"}
        valid_editorial_profiles = {"report", "classic"}
        if self.storage_type not in valid_storage:
            errors.append(f"STORAGE_TYPE?????レ챺???? ?????????덊렡: '{self.storage_type}' (???源낅츛: {valid_storage})")
        if self.editorial_profile not in valid_editorial_profiles:
            errors.append(
                f"EDITORIAL_PROFILE?????レ챺???? ?????????덊렡: '{self.editorial_profile}' "
                f"(???源낅츛: {valid_editorial_profiles})"
            )
        if not 1 <= self.schedule_minutes <= 1440:
            errors.append(f"SCHEDULE_INTERVAL_MINUTES ?類?????縕??? {self.schedule_minutes} (1~1440)")
        if not 1 <= self.country_parallel_limit <= 10:
            errors.append(f"COUNTRY_PARALLEL_LIMIT out of range: {self.country_parallel_limit} (1~10)")
        if self.daily_budget_usd < 0:
            errors.append(f"DAILY_BUDGET_USD??0 ???⑤?彛???⑤９苑????筌뤾퍓??? {self.daily_budget_usd}")
        if not 1 <= self.max_workers <= 50:
            errors.append(f"MAX_WORKERS ?類?????縕??? {self.max_workers} (1~50)")
        if not 1 <= self.limit <= 100:
            errors.append(f"DEFAULT_LIMIT ?類?????縕??? {self.limit} (1~100)")
        if not 1 <= self.notion_sem_limit <= 50:
            errors.append(f"NOTION_SEM_LIMIT ?類?????縕??? {self.notion_sem_limit} (1~50)")
        if not 1 <= self.data_retention_days <= 3650:
            errors.append(f"DATA_RETENTION_DAYS ?類?????縕??? {self.data_retention_days} (1~3650)")

        return errors

    def resolve_country_slug(self) -> str:
        """??? ?熬곣뫀????ｏ쭗?getdaytrends.com URL ??????쇱춻?용뿭큔 ?怨뚮뼚???"""
        return COUNTRY_MAP.get(self.country.lower(), self.country.lower())

    def for_country(self, country: str) -> "AppConfig":
        """癲ル슣????????????源놁젳???怨뚮옖甕????袁⑸즵???(???됰씭???좊읈? ?怨뚮옖筌??????덈틖??."""
        import dataclasses

        return dataclasses.replace(self, country=country, countries=[country])

    def get_effective_budget(self) -> float:
        """[C2] ??癰?????????レ챺?????????袁⑸즵??? ????ㅒ??22~07?? ??????????ル춪."""
        from datetime import datetime

        hour = datetime.now().hour
        if hour >= 22 or hour < 7:
            return self.daily_budget_usd * self.peak_budget_multiplier
        return self.daily_budget_usd

    def get_cache_ttl(self, peak_status: str = "") -> int:
        """[v10.0] peak_status ??れ삀??뫢?????깆뱾 癲????TTL (??癰??? ?袁⑸즵???"""
        return {
            "\uC0C1\uC2B9\uC911": self.cache_ttl_rising,
            "\uC815\uC810": self.cache_ttl_peak,
            "\uD558\uB77D\uC911": self.cache_ttl_falling,
        }.get(peak_status, self.cache_ttl_default)

    def get_generation_mode(self) -> str:
        """[v9.0] ??癰???? ??れ삀??뫢???獄쏅똻??癲ル슢?꾤땟????袁⑸즵???
        'full': ?潁뺛깺猷???????ш끽維????獄쏅똻??(???醫롮뵫 ??癰???
        'lite': ?????嶺뚮ㅎ?댐쭕?異?(????ㅒ??
        """
        if self.generation_mode_override in ("full", "lite"):
            return self.generation_mode_override
        from datetime import datetime

        hour = datetime.now().hour
        # ???醫롮뵫: ??ш끽維뽳ℓ?7-10), ?????12-14), ????19-22)
        if hour in range(7, 11) or hour in range(12, 15) or hour in range(19, 23):
            return "full"
        return "lite"

    def get_quality_threshold(self, content_group: str) -> int:
        """?熬곣뫕????????숆강筌?쓣爾?猿롫룱?QA 癲ル슔?됭짆????????袁⑸즵???"""
        return {
            "tweets": self.quality_feedback_min_score,
            "threads_posts": self.threads_quality_min_score,
            "long_posts": self.long_form_quality_min_score,
            "blog_posts": self.blog_quality_min_score,
        }.get(content_group, self.quality_feedback_min_score)

    def export_stats(self) -> dict:
        """[O3] ????筌먲퐡???筌믨퀡裕????源놁젳 ???ㅺ컼??????????깅탿."""
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
            "multi_country": {
                "enabled": self.enable_parallel_countries,
                "countries": self.countries,
                "parallel_limit": self.country_parallel_limit,
            },
            "features": {
                "clustering": self.enable_clustering,
                "long_form": self.enable_long_form,
                "threads": self.enable_threads,
                "smart_schedule": self.smart_schedule,
                "night_mode": self.night_mode,
                "adaptive_voice": self.enable_adaptive_voice,
                "tiered_collection": self.enable_tiered_collection,
                "golden_reference_qa": self.enable_golden_reference_qa,
                "trend_genealogy": self.enable_trend_genealogy,
                "edape": self.enable_edape,
                "tap": self.enable_tap,
                "streaming_pipeline": self.enable_streaming_pipeline,
            },
            "target_platforms": self.target_platforms,
            "enable_content_hub": self.enable_content_hub,
        }
