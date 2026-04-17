"""Category-relevance filter for news articles.

Extracted from the legacy ``scripts/news_bot.py`` (deprecated 2026-03-04)
so that active scripts can import the filter without pulling in the
full 1 200-line legacy module.

Usage::

    from antigravity_mcp.domain.category_filter import is_relevant_to_category

    if is_relevant_to_category(title, description, "Tech"):
        ...
"""

from __future__ import annotations

# ── Category keyword map ──
# RSS feeds often return mixed content (e.g., TechCrunch has fintech/legal,
# The Verge has politics/deals).  This keyword map rejects off-topic articles.

CATEGORY_KEYWORDS: dict[str, tuple[list[str], list[str]]] = {
    # (include_keywords, exclude_keywords)
    "Tech": (
        [
            "ai", "artificial intelligence", "software", "developer",
            "programming", "startup", "cloud", "saas", "api", "open source",
            "llm", "gpu", "chip", "semiconductor", "apple", "google",
            "microsoft", "amazon", "meta", "robot", "quantum",
            "cybersecurity", "hack", "browser", "linux", "python", "rust",
            "javascript", "database", "ml", "machine learning", "tech",
            "기술", "개발", "소프트웨어", "인공지능", "반도체", "클라우드",
            "스타트업", "오픈소스", "프로그래밍", "IT", "컴퓨터", "데이터",
        ],
        [
            "recipe", "cookbook", "fashion", "celebrity", "gossip",
            "horoscope", "sports score", "doordash", "food delivery",
        ],
    ),
    "Economy_KR": (
        [
            "경제", "금리", "증시", "코스피", "코스닥", "환율", "부동산",
            "물가", "한국은행", "기재부", "수출", "수입", "GDP", "고용",
            "실업", "투자", "주가", "채권", "무역", "산업", "기업",
            "삼성", "현대", "SK", "LG", "배당", "IPO", "상장",
            "은행", "보험", "카드", "대출", "저축", "연금", "세금",
            "재정", "매출", "영업이익", "순이익", "실적", "분기", "반기",
            "결산", "소비", "소비자", "가격", "할인", "쇼핑", "유통",
            "마트", "백화점", "시장", "거래", "매매", "분양", "아파트",
            "전세", "월세", "임대", "주식", "펀드", "ETF", "증권",
            "자산", "포트폴리오", "수출입", "관세", "FTA", "무역수지",
            "경상수지", "인플레이션", "디플레이션", "스태그플레이션",
            "경기", "불황", "호황", "신한", "국민", "하나", "우리",
            "농협", "카카오", "네이버", "쿠팡", "포스코", "롯데", "CJ",
            "신세계", "GS", "KT", "셀트리온", "바이오", "속보", "전망",
            "전년", "증가", "감소", "상승", "하락", "급등", "급락",
        ],
        [],
    ),
    "Economy_Global": (
        [
            "economy", "gdp", "inflation", "fed", "interest rate", "stock",
            "market", "trade", "tariff", "treasury", "bond", "wall street",
            "nasdaq", "s&p", "dow", "earnings", "revenue", "fiscal",
            "monetary", "central bank", "ecb", "imf", "world bank",
            "recession", "growth", "employment", "jobs", "oil", "commodity",
            "forex",
        ],
        ["celebrity", "sports", "entertainment"],
    ),
    "Crypto": (
        [
            "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain",
            "defi", "nft", "token", "web3", "mining", "staking", "wallet",
            "exchange", "binance", "coinbase", "solana", "xrp", "altcoin",
            "비트코인", "이더리움", "암호화폐", "블록체인", "코인", "거래소",
            "디파이", "토큰", "스테이킹", "채굴",
        ],
        [],
    ),
    "Global_Affairs": (
        [
            "war", "peace", "treaty", "sanction", "diplomacy", "election",
            "president", "minister", "parliament", "united nations", "nato",
            "refugee", "conflict", "military", "nuclear", "human rights",
            "immigration", "border", "protest", "coup", "summit",
            "ambassador", "외교", "전쟁", "평화", "정상회담", "유엔",
            "군사", "난민", "제재",
        ],
        ["recipe", "fashion", "sports score"],
    ),
    "AI_Deep": (
        [
            "ai", "artificial intelligence", "llm", "gpt", "claude",
            "gemini", "transformer", "diffusion", "agent", "rag",
            "fine-tune", "training", "inference", "benchmark",
            "open source model", "foundation model", "multimodal",
            "reasoning", "alignment", "safety", "rlhf", "mcp",
            "langchain", "hugging face", "openai", "anthropic",
            "google ai", "meta ai", "deepmind", "mistral", "deepseek",
            "prompt", "인공지능", "대규모 언어 모델", "에이전트",
            "파인튜닝", "추론",
        ],
        ["recipe", "fashion", "celebrity", "sports"],
    ),
}


def is_relevant_to_category(title: str, description: str, category: str) -> bool:
    """Check if an article is relevant to its assigned category.

    Returns ``True`` when *title + description* matches at least one
    include-keyword and none of the exclude-keywords for *category*.
    Unknown categories are accepted unconditionally.
    """
    keywords_map = CATEGORY_KEYWORDS.get(category)
    if not keywords_map:
        return True  # unknown category → accept all

    include_kw, exclude_kw = keywords_map
    text = (title + " " + description).lower()

    for kw in exclude_kw:
        if kw in text:
            return False

    for kw in include_kw:
        if kw in text:
            return True

    return False

