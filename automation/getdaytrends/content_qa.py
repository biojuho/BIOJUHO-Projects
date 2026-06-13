"""
getdaytrends — Content QA & Regeneration
콘텐츠 QA 감사 + 재생성 로직.
generator.py에서 분리됨.
"""

import asyncio
import contextlib
import re
import unicodedata

from loguru import logger as log

from shared.llm import LLMClient
from shared.llm.models import LLMPolicy

try:
    from .config import AppConfig
    from .models import GeneratedTweet, ScoredTrend, TweetBatch
    from .multilang import (
        _BLOG_REQUIRED_HEADINGS,
        _GENERIC_ENTITY_ALLOWLIST,
        _QA_CLICHE_PATTERNS,
        _THREADS_BAIT_PATTERNS,
        _build_allowed_fact_corpus,
        _extract_candidate_entities,
        _first_nonempty_lines,
    )
except ImportError:
    from config import AppConfig
    from models import GeneratedTweet, ScoredTrend, TweetBatch
    from multilang import (
        _BLOG_REQUIRED_HEADINGS,
        _GENERIC_ENTITY_ALLOWLIST,
        _QA_CLICHE_PATTERNS,
        _THREADS_BAIT_PATTERNS,
        _build_allowed_fact_corpus,
        _extract_candidate_entities,
        _first_nonempty_lines,
    )

_JSON_POLICY = LLMPolicy(response_mode="json")


_UNVERIFIED_QUOTE_PATTERNS = [
    "전문가들은",
    "관계자에 따르면",
    "업계 관계자",
    "한 관계자는",
    "내부 소식통",
    "익명의 관계자",
    "소식통에 따르면",
    "전문가는 분석",
]
_SOURCE_QUANTIFIER_RE = (
    r"(?:(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|several|multiple|some|various)\s+)?"
)
_UNVERIFIED_ATTRIBUTION_REGEXES = (
    re.compile(
        r"\b(?:sources?|insiders?)\s+"
        r"(?:say|says|said|tell|tells|told|claim|claims|claimed|report|reports|reported|"
        r"indicate|indicates|indicated|suggest|suggests|suggested|"
        r"believe|believes|believed|expect|expects|expected)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b"
        + _SOURCE_QUANTIFIER_RE
        + r"(?:person|people|officials?)\s+"
        r"(?:say|says|said|tell|tells|told|claim|claims|claimed|report|reports|reported|"
        r"indicate|indicates|indicated|suggest|suggests|suggested|"
        r"believe|believes|believed|expect|expects|expected)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\baccording\s+to\s+"
        + _SOURCE_QUANTIFIER_RE
        + r"(?:sources?|insiders?|unnamed\s+officials?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bunnamed\s+officials?\s+(?:say|said|claim|claimed|report|reported)\b", re.IGNORECASE),
    re.compile(r"\breportedly\b", re.IGNORECASE),
    re.compile(r"\ballegedly\b", re.IGNORECASE),
    re.compile(
        r"\b(?:is|are|was|were|has\s+been|have\s+been)\s+"
        r"(?:said|believed|reported|expected|rumou?red|alleged|understood|thought|tipped)\s+to\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bit\s+(?:is|was|has\s+been|had\s+been)\s+"
        r"(?:said|believed|reported|expected|rumou?red|alleged|understood|thought)\s+that\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:a\s+)?(?:person|people|sources?)\s+familiar\s+with\s+(?:the\s+)?"
        r"(?:matter|plans?|decision|discussions?|talks?|negotiations?|situation|deal)\s+"
        r"(?:say|says|said|tell|tells|told|claim|claims|claimed|report|reports|reported)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\baccording\s+to\s+"
        + _SOURCE_QUANTIFIER_RE
        + r"(?:person|people|sources?)\s+"
        r"familiar\s+with\s+(?:the\s+)?"
        r"(?:matter|plans?|decision|discussions?|talks?|negotiations?|situation|deal)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:a\s+)?(?:person|people|sources?|insiders?)\s+"
        r"(?:briefed\s+on|with\s+(?:direct\s+|first-?hand\s+)?knowledge\s+of|close\s+to)\s+"
        r"(?:the\s+)?(?:matter|plans?|decision|discussions?|talks?|negotiations?|situation|deal)\s+"
        r"(?:say|says|said|tell|tells|told|claim|claims|claimed|report|reports|reported|"
        r"indicate|indicates|indicated|suggest|suggests|suggested)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\baccording\s+to\s+"
        + _SOURCE_QUANTIFIER_RE
        + r"(?:person|people|sources?|insiders?)\s+"
        r"(?:briefed\s+on|with\s+(?:direct\s+|first-?hand\s+)?knowledge\s+of|close\s+to)\s+"
        r"(?:the\s+)?(?:matter|plans?|decision|discussions?|talks?|negotiations?|situation|deal)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:a\s+)?(?:source|person|official|insider)\s+"
        r"(?:speaking|spoke)\s+on\s+condition\s+of\s+anonymity\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:a\s+|an\s+)?(?:source|person|people|officials?|insiders?)\s+"
        r"(?:who\s+)?(?:was\s+|were\s+)?not\s+authorized\s+to\s+"
        r"(?:speak\s+publicly|discuss\s+(?:the\s+)?matter)\s+"
        r"(?:say|says|said|tell|tells|told|claim|claims|claimed|report|reports|reported|"
        r"indicate|indicates|indicated|suggest|suggests|suggested)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:a\s+)?(?:source|person|people|officials?|insiders?)\s+"
        r"(?:who\s+)?asked\s+not\s+to\s+be\s+named\s+"
        r"(?:say|says|said|tell|tells|told|claim|claims|claimed|report|reports|reported|"
        r"indicate|indicates|indicated|suggest|suggests|suggested)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:the\s+)?(?:source|person|official|insider)\s+"
        r"(?:requested\s+anonymity|declined\s+to\s+be\s+identified|spoke\s+anonymously)"
        r"[^.!?\n]{0,80}?\b(?:say|says|said|tell|tells|told|claim|claims|claimed|report|reports|reported|"
        r"indicate|indicates|indicated|suggest|suggests|suggested)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:several|multiple)?\s*(?:media\s+)?reports?\s+"
        r"(?:say|says|said|suggest|suggests|suggested|indicate|indicates|"
        r"indicated|claim|claims|claimed|reported)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:a\s+|an\s+)?(?:media\s+outlets?|news\s+outlets?|newswires?|local\s+media|press)\s+"
        r"(?:say|says|said|tell|tells|told|claim|claims|claimed|report|reports|reported|"
        r"indicate|indicates|indicated|suggest|suggests|suggested)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:analysts?|experts?|observers?|commentators?|watchers?)\s+"
        r"(?:say|says|said|believe|believes|believed|expect|expects|expected|"
        r"forecast|forecasts|forecasted|project|projects|projected|"
        r"predict|predicts|predicted|estimate|estimates|estimated|suggest|suggests|suggested)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\baccording\s+to\s+(?:analysts?|experts?|observers?|commentators?|watchers?)\b", re.IGNORECASE),
    re.compile(r"\bwall\s+street\s+is\s+betting\s+on\b", re.IGNORECASE),
    re.compile(r"\b(?:investors?|traders?)\s+(?:expect|expects|expected|are\s+pricing\s+in|price\s+in|priced\s+in)\b", re.IGNORECASE),
    re.compile(r"\b(?:the\s+)?market\s+sees\b", re.IGNORECASE),
    re.compile(r"\bconsensus\s+(?:points|pointed|is\s+pointing)\s+to\b", re.IGNORECASE),
    re.compile(r"\b(?:bulls|bears)\s+(?:say|says|said|believe|believes|expect|expects|argue|argues)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:leaked|internal|confidential)\s+"
        r"(?:documents?|memos?|roadmaps?|slides?|filings?)\s+"
        r"(?:say|says|said|show|shows|showed|suggest|suggests|suggested|"
        r"claim|claims|claimed|indicate|indicates|reveal|reveals|revealed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:a\s+|an\s+|the\s+)?(?:draft\s+)?"
        r"(?:document|filing|memo|email|presentation|slide\s+deck|slides?|spreadsheet|material|record|screenshot)\s+"
        r"(?:say|says|said|show|shows|showed|suggest|suggests|suggested|"
        r"claim|claims|claimed|indicate|indicates|indicated|reveal|reveals|revealed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:a\s+|an\s+)?(?:draft\s+)?"
        r"(?:documents?|emails?|memos?|slides?|filings?|presentations?|materials?|records?)\s+"
        r"(?:seen|viewed|obtained|reviewed|examined)\s+by\s+[^.!?\n]{1,40}?\s+"
        r"(?:say|says|said|show|shows|showed|suggest|suggests|suggested|"
        r"claim|claims|claimed|indicate|indicates|reveal|reveals|revealed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:according\s+to|based\s+on|citing)\s+(?:a\s+|an\s+)?(?:draft\s+)?"
        r"(?:documents?|emails?|memos?|slides?|filings?|presentations?|materials?|records?)\s+"
        r"(?:seen|viewed|obtained|reviewed|examined)\s+by\s+[^.!?\n]{1,40}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:reporters?|journalists?|outlets?|media)\s+"
        r"(?:saw|viewed|obtained|reviewed|examined)\s+(?:a\s+|an\s+)?(?:draft\s+)?"
        r"(?:documents?|emails?|memos?|slides?|filings?|presentations?|materials?|records?)\s+"
        r"(?:showing|saying|suggesting|claiming|indicating|revealing|that)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:rumou?rs?|speculation|market\s+chatter|industry\s+chatter|whispers?)\s+"
        r"(?:say|says|said|suggest|suggests|suggested|claim|claims|claimed|"
        r"point|points|pointed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:a\s+|an\s+|the\s+)?"
        r"(?:social\s+media\s+posts?|online\s+posts?|community\s+posts?|forum\s+posts?|"
        r"posts?|comments?|threads?|discussion\s+threads?)\s+"
        r"(?:say|says|said|suggest|suggests|suggested|claim|claims|claimed|"
        r"indicate|indicates|indicated|point|points|pointed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:a\s+|an\s+|the\s+)?"
        r"(?:survey|poll|study|report|dataset|tracker)\s+"
        r"(?:show|shows|showed|find|finds|found|suggest|suggests|suggested|"
        r"indicate|indicates|indicated|claim|claims|claimed|point|points|pointed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![A-Za-z0-9.]\s)\b(?:the\s+)?(?:data|figures?|numbers?)\s+"
        r"(?:show|shows|showed|find|finds|found|suggest|suggests|suggested|"
        r"indicate|indicates|indicated|claim|claims|claimed|point|points|pointed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        "(?:\\uc720\\ucd9c|\\ub0b4\\ubd80|\\ube44\\uacf5\\uac1c)\\s*"
        "(?:\\ubb38\\uc11c|\\ubb38\\uac74|\\uba54\\ubaa8|\\uc790\\ub8cc|\\ub85c\\ub4dc\\ub9f5)\\s*"
        "(?:\\uc5d0\\s*\\ub530\\ub974\\uba74|\\uc5d0\\s*\\uc758\\ud558\\uba74)",
        re.IGNORECASE,
    ),
    re.compile(
        "(?:\\uc628\\ub77c\\uc778\\s*)?(?:\\ub8e8\\uba38|\\uc18c\\ubb38|\\ucd94\\uce21)\\s*"
        "(?:\\uc5d0\\s*\\ub530\\ub974\\uba74|\\uc5d0\\s*\\uc758\\ud558\\uba74)",
        re.IGNORECASE,
    ),
    re.compile(
        "(?:\\uc804\\ubb38\\uac00\\ub4e4?|\\ubd84\\uc11d\\uac00\\ub4e4?|"
        "\\uc560\\ub110\\ub9ac\\uc2a4\\ud2b8\\ub4e4?|\\uc5c5\\uacc4\\s*"
        "\\uad00\\uacc4\\uc790\\ub4e4?|\\uc2dc\\uc7a5\\s*\\uad00\\uacc4\\uc790\\ub4e4?)\\s*"
        "(?:\\uc740|\\ub294|\\uc774|\\uac00)?[^.!?\\n]{0,80}"
        "(?:\\ub9d0\\ud55c\\ub2e4|\\ub9d0\\ud588\\ub2e4|\\ubcf4\\uace0\\s*\\uc788\\ub2e4|"
        "\\ubd84\\uc11d\\ud55c\\ub2e4|\\uc608\\uc0c1\\ud55c\\ub2e4|\\uc804\\ub9dd\\ud55c\\ub2e4|"
        "\\ucd94\\uc815\\ud55c\\ub2e4|\\ubc1d\\ud614\\ub2e4)",
        re.IGNORECASE,
    ),
    re.compile(
        "(?:\\ubcf5\\uc218\\uc758\\s*)?(?:\\uc5b8\\ub860\\s*)?(?:\\ub9e4\\uccb4\\s*)?"
        "\\ubcf4\\ub3c4\\s*(?:\\uc5d0\\s*\\ub530\\ub974\\uba74|\\uc5d0\\s*\\uc758\\ud558\\uba74)",
        re.IGNORECASE,
    ),
    re.compile(
        "(?:\\uad00\\uacc4\\uc790\\ub4e4?|\\uc18c\\uc2dd\\ud1b5\\ub4e4?)\\s*"
        "(?:\\uc5d0\\s*\\ub530\\ub974\\uba74|\\uc5d0\\s*\\uc758\\ud558\\uba74)",
        re.IGNORECASE,
    ),
    re.compile(
        "\\uac83\\uc73c\\ub85c\\s*"
        "(?:\\uc54c\\ub824\\uc84c\\ub2e4|\\uc804\\ud574\\uc84c\\ub2e4|\\uc804\\ub9dd\\ub41c\\ub2e4)",
        re.IGNORECASE,
    ),
)
_DOMAIN_CANDIDATE_RE = re.compile(
    r"(?<![@\w.-])(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?",
    re.IGNORECASE,
)
_DOMAIN_ATTRIBUTION_REGEXES = (
    re.compile(
        r"(?m)^\s*(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s:]*)?\s*(?::|[-\u2013\u2014])",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![@\w.-])(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?"
        r"\s+(?:reports?|reported|says?|said|claims?|claimed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![@\w.-])(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?"
        r"\s+(?:data|figures?|numbers?|reports?|analysis)\s+"
        r"(?:shows?|showed|suggests?|suggested|indicates?|indicated|finds?|found)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:data|figures?|numbers?|reports?|analysis)\s+from\s+"
        r"(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\baccording\s+to\s+(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:as\s+)?per\s+(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![@\w.-])(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?"
        r"\s*(?:에\s*따르면|보도에\s*따르면)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bvia\s+(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\breported\s+by\s+(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bciting\s+(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsource\s*[:=-]\s*(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:출처|근거)\s*[:=-]\s*(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?",
        re.IGNORECASE,
    ),
)
_OUTLET_NAME_RE = (
    r"(?:the\s+)?(?:financial\s+times|wall\s+street\s+journal|new\s+york\s+times|washington\s+post|guardian)"
    r"|reuters|bloomberg|yonhap|bbc|cnn|cnbc|forbes|nikkei|wsj|ap\s+news|associated\s+press"
)
_OUTLET_NAME_PATTERN = re.compile(r"\b(" + _OUTLET_NAME_RE + r")\b", re.IGNORECASE)
_OUTLET_ATTRIBUTION_REGEXES = (
    re.compile(
        r"\b(" + _OUTLET_NAME_RE + r")\s+(?:reports?|reported|says?|said|claims?|claimed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(" + _OUTLET_NAME_RE + r")\s+(?:data|figures?|numbers?|reports?|analysis)\s+"
        r"(?:shows?|showed|suggests?|suggested|indicates?|indicated|finds?|found)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:data|figures?|numbers?|reports?|analysis)\s+from\s+(" + _OUTLET_NAME_RE + r")\b",
        re.IGNORECASE,
    ),
    re.compile(r"\baccording\s+to\s+(" + _OUTLET_NAME_RE + r")\b", re.IGNORECASE),
    re.compile(r"\b(?:as\s+)?per\s+(" + _OUTLET_NAME_RE + r")\b", re.IGNORECASE),
    re.compile(r"\breported\s+by\s+(" + _OUTLET_NAME_RE + r")\b", re.IGNORECASE),
    re.compile(r"\bciting\s+(" + _OUTLET_NAME_RE + r")\b", re.IGNORECASE),
)
_ATTRIBUTION_MARKER_ALLOWLIST = {
    "as",
    "citing",
    "analysis",
    "data",
    "figure",
    "figures",
    "number",
    "numbers",
    "per",
    "report",
    "reports",
    "source",
    "via",
    "\ucd9c\ucc98",
    "\uadfc\uac70",
}

_BANNED_SLANG_PATTERNS = (
    "쩌리",
    "똥챔프",
    "깝치",
    "현타",
)

_EMOJI_RANGES = (
    (0x1F300, 0x1FAFF),
    (0x2600, 0x27BF),
)

_AI_NATIVE_PATTERNS = (
    r"\bai\b",
    r"\bgpt\b",
    r"\bllm\b",
    r"\bagent(?:s)?\b",
    r"\bmodel(?:s)?\b",
    r"\bclaude\b",
    r"\bopenai\b",
    r"\bgemini\b",
    "인공지능",
    "생성형",
    "에이전트",
    "모델",
)

_PROHIBITED_ANALOGY_PATTERNS = (
    re.compile(r"\b마치\b"),
    re.compile(r"(?<![가-힣A-Za-z0-9])\S+\s*같(?:다|은|이|고|지만|습니다)"),
    re.compile(r"(?<![가-힣A-Za-z0-9])\S+\s*처럼"),
    re.compile(r"(?<![가-힣A-Za-z0-9])\S+\s*듯(?:하다|한|이|습니다|지만)?"),
    re.compile(r"\bas if\b", re.IGNORECASE),
    re.compile(r"\blike an?\b", re.IGNORECASE),
    re.compile(r"\b(?:analogy|metaphor)\b", re.IGNORECASE),
)

_CONCRETE_NUMBER_CLAIM_RE = re.compile(
    r"(?<![\w.])(?:[$€£₩]\s*)?\d+(?:[,.]\d{3})*(?:\.\d+)?\s*"
    r"(?:billion|million|trillion|bn|usd|krw|won|dollars?|users?|people|stores?|"
    r"companies?|countries?|years?|days?|hours?)\b",
    re.IGNORECASE,
)
_CURRENCY_NUMBER_CLAIM_RE = re.compile(
    r"(?<![\w.])(?:[$\u20ac\u00a3\u20a9]\s*)\d+(?:[,.]\d{3})*(?:\.\d+)?",
    re.IGNORECASE,
)
_SIGNIFICANT_BARE_NUMBER_CLAIM_RE = re.compile(
    r"(?<![\w.$\u20ac\u00a3\u20a9-])(?:\d{1,3}(?:,\d{3})+|\d{5,})(?![\w.%])",
    re.IGNORECASE,
)
_PERCENTAGE_CLAIM_RE = re.compile(
    r"(?<![\d.])\d+(?:\.\d+)?\s*(?:%|퍼센트|프로)(?![\d.])",
)
_KOREAN_NUMBER_CLAIM_RE = re.compile(
    r"(?<![\d.])\d+(?:[,.]\d{3})*(?:\.\d+)?\s*(?:만|억|조)?\s*"
    r"(?:개월|시간|달러|원|명|건|곳|대|회|개|년|일)(?![\d.])",
)
_EXPLICIT_DATE_CLAIM_RE = re.compile(
    r"\b(?:"
    r"\d{4}-\d{1,2}-\d{1,2}|"
    r"\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+"
    r"\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?|"
    r"\d{1,2}(?:st|nd|rd|th)?\s+"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r")\b",
    re.IGNORECASE,
)
_KOREAN_DATE_CLAIM_RE = re.compile(
    r"(?<!\d)(?:\d{4}년\s*)?\d{1,2}월\s*\d{1,2}일(?!\d)",
)


_STRONG_CLAIM_REGEXES = (
    re.compile(r"\b(?:record|all-time)\s+(?:high|low)\b", re.IGNORECASE),
    re.compile(r"\ball[-\s]time\s+record\b", re.IGNORECASE),
    re.compile(r"\brecord[-\s]breaking\b", re.IGNORECASE),
    re.compile(
        r"\bunprecedented\s+"
        r"(?:levels?|demand|growth|surge|orders?|cycle|highs?|lows?|pace|scale|volume|momentum)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bhistoric\s+"
        r"(?:high|low|levels?|demand|growth|surge|orders?|cycle|pace|scale|volume|momentum)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bbest\s+"
        r"(?:quarter|month|week|day|year|performance|run|streak|result|showing|sales?|growth|demand|orders?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:new|fresh)\s+(?:high|low|peak|trough)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:hit|reached|climbed\s+to|rose\s+to|jumped\s+to|surged\s+to)\s+"
        r"(?:a\s+)?(?!(?:new|fresh)\s)peak\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:no\.?|number)\s*(?:1|one)\b", re.IGNORECASE),
    re.compile(r"\btop[-\s](?:ranked|rank|ranking|spot|position)\b", re.IGNORECASE),
    re.compile(
        r"\bmost\s+valuable\s+"
        r"(?:company|chipmaker|stock|brand|firm|startup|asset|token|coin|team)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:overtook|surpassed)\s+(?:rivals?|competitors?|peers?)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:will|would|could|may|might)\s+"
        r"(?:dominate|double|triple|reshape|transform|redefine|explode|skyrocket|keep\s+rising|keep\s+growing)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:is|are|was|were|looks|seems)?\s*"
        r"(?:set|poised|on\s+track|guaranteed)\s+to\s+"
        r"(?:dominate|double|triple|reshape|transform|redefine|explode|skyrocket|"
        r"keep\s+rising|keep\s+growing|become|win)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:could|may|might|will|would)\s+become\s+the\s+next\s+"
        r"[a-z][a-z0-9&.\- ]{0,50}?\s*(?:winner|giant|leader|unicorn|megacap)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:outpaced|outpaces|outpacing)\s+(?:rivals?|competitors?|peers?)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:beat|beats|beating|topped|tops|topping|exceeded|exceeds|exceeding)\s+"
        r"(?:analyst\s+)?expectations\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:stronger|better|faster|more\s+powerful|more\s+valuable|more\s+profitable)\s+"
        r"than\s+(?:rivals?|competitors?|peers?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bleft\s+(?:rivals?|competitors?|peers?)\s+behind\b", re.IGNORECASE),
    re.compile(r"\b(?:widened|widening|extended|extends|extending)\s+(?:its|the|a)\s+lead\b", re.IGNORECASE),
    re.compile(
        r"\b(?:sparked|triggered|ignited|caused)\s+(?:a\s+)?"
        r"(?:rally|selloff|surge|jump|drop|boom|rush|panic|demand\s+surge)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:fueled|fuelled)\s+(?:investor\s+)?(?:optimism|panic|demand|rally|selloff)\b", re.IGNORECASE),
    re.compile(r"\bsent\s+(?:shares?|stocks?|markets?)\s+(?:higher|lower|up|down)\b", re.IGNORECASE),
    re.compile(
        r"\bpushed\s+(?:the\s+)?(?:stock|stocks?|shares?|market|markets?)\s+"
        r"(?:up|down|higher|lower)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bdrove\s+(?:market\s+)?(?:gains|losses|rally|selloff|demand|optimism)\b", re.IGNORECASE),
    re.compile(r"\bmade\s+investors\s+(?:rush\s+in|pile\s+in|buy|sell)\b", re.IGNORECASE),
    re.compile(
        r"\bcaused\s+[a-z][a-z0-9&.\- ]{0,40}?\s+to\s+"
        r"(?:surge|jump|drop|rise|fall|explode|slump)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bgame[-\s]changer\b", re.IGNORECASE),
    re.compile(r"\bturning\s+point\b", re.IGNORECASE),
    re.compile(r"\bbreakthrough\s+(?:moment|shift|development|event|milestone)\b", re.IGNORECASE),
    re.compile(r"\bseismic\s+shift\b", re.IGNORECASE),
    re.compile(r"\bchanges\s+everything\b", re.IGNORECASE),
    re.compile(r"\bmassive\s+tailwind\b", re.IGNORECASE),
    re.compile(r"\b(?:opened|opens|ushered\s+in|ushers\s+in)\s+(?:a\s+)?new\s+era\b", re.IGNORECASE),
    re.compile(r"\bwatershed\s+moment\b", re.IGNORECASE),
    re.compile(r"\beveryone\s+is\s+talking\s+about\b", re.IGNORECASE),
    re.compile(
        r"\b(?:the\s+)?internet\s+(?:went\s+wild|lost\s+it|is\s+losing\s+it)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bsparked\s+(?:online\s+)?(?:debate|backlash|discussion|controversy)\b", re.IGNORECASE),
    re.compile(r"\bdivided\s+(?:investors?|fans?|users?|viewers?|analysts?)\b", re.IGNORECASE),
    re.compile(r"\btalk\s+of\s+the\s+internet\b", re.IGNORECASE),
    re.compile(r"\bsocial\s+media\s+erupted\b", re.IGNORECASE),
    re.compile(
        r"\bsent\s+(?:users?|fans?|investors?|viewers?)\s+into\s+(?:a\s+)?frenzy\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bdominated\s+(?:the\s+)?conversation\b", re.IGNORECASE),
    re.compile(r"\b(?:went|goes|going)\s+viral\b", re.IGNORECASE),
    re.compile(r"\b(?:blew|blown|blowing)\s+up\s+(?:online|on\s+social\s+media)\b", re.IGNORECASE),
    re.compile(r"\bbroke\s+the\s+internet\b", re.IGNORECASE),
    re.compile(r"\btook\s+social\s+media\s+by\s+storm\b", re.IGNORECASE),
    re.compile(r"\bcaught\s+fire\s+online\b", re.IGNORECASE),
    re.compile(r"\bset\s+social\s+media\s+ablaze\b", re.IGNORECASE),
    re.compile(r"\bbecame\s+(?:a\s+)?meme\b", re.IGNORECASE),
    re.compile(
        r"\bproved\s+[a-z][a-z0-9&.\- ]{0,60}?\s+(?:is|are|was|were)\s+"
        r"(?:real|true|valid)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:confirmed|validated)\s+(?:the\s+)?(?:[a-z0-9&.\-]+\s+){0,4}"
        r"(?:boom|thesis|narrative|story|case|trend|demand)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bput\s+doubts\s+to\s+rest\b", re.IGNORECASE),
    re.compile(r"\b(?:ended|settled)\s+the\s+debate\b", re.IGNORECASE),
    re.compile(r"\bsilenced\s+skeptics\b", re.IGNORECASE),
    re.compile(r"\bremoved\s+uncertainty\b", re.IGNORECASE),
    re.compile(r"\b(?:is|was|became|becomes|looks|looked)\s+(?:inevitable|unstoppable)\b", re.IGNORECASE),
    re.compile(r"\b(?:no[-\s]?brainer|sure\s+bet|safe\s+bet)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:can't|cannot|can\s+not)[-\s]?miss\s+"
        r"(?:trade|stock|buy|investment|opportunity)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bmust[-\s]have\s+(?:for\s+)?(?:portfolios?|investors?|buyers?|customers?)\b", re.IGNORECASE),
    re.compile(r"\b(?:investors?|buyers?|traders?)\s+(?:can't|cannot|can\s+not)\s+lose\s+with\b", re.IGNORECASE),
    re.compile(r"\b(?:flashed|triggered|gave|sent)\s+(?:a\s+)?buy\s+signal\b", re.IGNORECASE),
    re.compile(r"\bgave\s+(?:investors?|traders?|the\s+market)\s+(?:a\s+)?green\s+light\b", re.IGNORECASE),
    re.compile(r"\bgave\s+(?:investors?|traders?|the\s+market)\s+(?:an\s+)?all[-\s]?clear\b", re.IGNORECASE),
    re.compile(
        r"\b(?:showed|shows|signaled|signals)\s+(?:it\s+is|it's)\s+time\s+to\s+buy\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:created|creates|opened|opens)\s+(?:a\s+)?buying\s+opportunity\b", re.IGNORECASE),
    re.compile(r"\b(?:offered|offers|created|creates)\s+(?:a\s+)?perfect\s+entry\s+point\b", re.IGNORECASE),
    re.compile(r"\b(?:investors?|traders?)\s+should\s+(?:load\s+up|double\s+down)\s+on\b", re.IGNORECASE),
    re.compile(r"\b(?:is|was|looks|looked|became|becomes)\s+(?:undervalued|overvalued)\b", re.IGNORECASE),
    re.compile(r"\blooks?\s+(?:cheap|expensive)\b", re.IGNORECASE),
    re.compile(r"\bis\s+(?:a\s+)?bargain\b", re.IGNORECASE),
    re.compile(r"\bhas\s+(?:meaningful\s+|major\s+|more\s+)?(?:upside|downside)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:price\s+target|target\s+price)\s+"
        r"(?:moved|moves|points?|pointed|is|was)\s+(?:higher|lower|up|down)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bvaluation\s+(?:looks?|looked|is|was)\s+(?:stretched|rich|cheap|expensive)\b", re.IGNORECASE),
    re.compile(r"\bpriced\s+for\s+perfection\b", re.IGNORECASE),
    re.compile(r"\bhas\s+room\s+to\s+run\b", re.IGNORECASE),
    re.compile(
        r"\b(?:is|are|was|were|got|gets|has\s+been|have\s+been)\s+"
        r"(?:upgraded|downgraded)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:wall\s+street|analysts?|brokers?)\s+(?:upgraded|downgraded)\b", re.IGNORECASE),
    re.compile(r"\b(?:moody'?s|s&p|s\s*&\s*p|fitch)\s+(?:upgraded|downgraded)\s+[a-z0-9&.'-]+\b", re.IGNORECASE),
    re.compile(
        r"\b(?:moody'?s|s&p|s\s*&\s*p|fitch)\s+put\s+[a-z0-9&.'-]+\s+on\s+"
        r"(?:negative|positive)\s+watch\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:moody'?s|s&p|s\s*&\s*p|fitch)\s+(?:raised|lowered)\s+[a-z0-9&.'-]+\s+outlook\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:earned|landed|kept|received|got|gets|holds?|held)\s+(?:a\s+)?"
        r"(?:buy|sell|hold|neutral|outperform|underperform)\s+rating\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:moved|moves)\s+to\s+(?:outperform|underperform|neutral|buy|sell|hold)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:is|are|was|were|got|gets|has\s+been|have\s+been)\s+"
        r"(?:cut|raised|lowered)\s+to\s+(?:buy|sell|hold|neutral|outperform|underperform)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:is|are|was|were|has\s+been|have\s+been)\s+initiated\s+"
        r"(?:at|with)\s+(?:a\s+)?(?:buy|sell|hold|neutral|outperform|underperform)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:beat|beats|missed|misses|miss)\s+"
        r"(?:earnings|revenue|sales|profit|profits|eps)\s+"
        r"(?:estimates?|expectations?|forecasts?|targets?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\btopped\s+(?:the\s+)?ai\s+benchmark\s+leaderboard\b", re.IGNORECASE),
    re.compile(r"\bachieved\s+state[-\s]of[-\s]the[-\s]art\s+performance\b", re.IGNORECASE),
    re.compile(r"\bmodel\s+beat\s+benchmark\s+records\b", re.IGNORECASE),
    re.compile(r"\breduced\s+inference\s+latency\b", re.IGNORECASE),
    re.compile(r"\bdoubled\s+inference\s+throughput\b", re.IGNORECASE),
    re.compile(r"\bcut\s+training\s+costs\b", re.IGNORECASE),
    re.compile(r"\blowered\s+token\s+costs\b", re.IGNORECASE),
    re.compile(r"\bimproved\s+energy\s+efficiency\b", re.IGNORECASE),
    re.compile(r"\bposted\s+(?:the\s+)?best\s+benchmark\s+accuracy\b", re.IGNORECASE),
    re.compile(r"\bpassed\s+(?:a\s+)?safety\s+evaluation\b", re.IGNORECASE),
    re.compile(r"\blowered\s+hallucination\s+rates\b", re.IGNORECASE),
    re.compile(r"\bdelivered\s+(?:a\s+)?major\s+speedup\b", re.IGNORECASE),
    re.compile(
        r"\b(?:raised|raises|cut|cuts|lowered|lowers|lifted|lifts)\s+"
        r"(?:its\s+|the\s+)?(?:guidance|outlook|forecast)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:issued|issues)\s+(?:a\s+)?(?:profit|margin|revenue|earnings)\s+warning\b", re.IGNORECASE),
    re.compile(r"\bwarned\s+on\s+(?:profits?|margins?|revenue|earnings|sales)\b", re.IGNORECASE),
    re.compile(r"\b(?:revenue|profits?|sales|orders)\s+(?:doubled|tripled)\b", re.IGNORECASE),
    re.compile(r"\bprofits?\s+surged\b", re.IGNORECASE),
    re.compile(r"\bmargins?\s+expanded\b", re.IGNORECASE),
    re.compile(r"\bgross\s+margin\s+hit\b", re.IGNORECASE),
    re.compile(r"\bfree\s+cash\s+flow\s+turned\s+positive\b", re.IGNORECASE),
    re.compile(r"\breturned\s+to\s+profitability\b", re.IGNORECASE),
    re.compile(r"\breported\s+record\s+revenue\b", re.IGNORECASE),
    re.compile(r"\bsales\s+crossed\b", re.IGNORECASE),
    re.compile(r"\bebitda\s+improved\b", re.IGNORECASE),
    re.compile(r"\boperating\s+income\s+jumped\b", re.IGNORECASE),
    re.compile(r"\bbacklog\s+reached\b", re.IGNORECASE),
    re.compile(r"\border\s+backlog\s+hit\s+(?:a\s+)?record\b", re.IGNORECASE),
    re.compile(r"\bbacklog\s+exceeded\s+supply\b", re.IGNORECASE),
    re.compile(
        r"\b(?:recorded|booked|took)\s+(?:a\s+|an\s+)?"
        r"(?:impairment|restructuring|warranty|one[-\s]time|non[-\s]cash)\s+charge\b",
        re.IGNORECASE,
    ),
    re.compile(r"\btook\s+(?:a\s+|an\s+)?goodwill\s+impairment\b", re.IGNORECASE),
    re.compile(r"\bwrote\s+(?:down|off)\s+(?:obsolete\s+)?inventory\b", re.IGNORECASE),
    re.compile(r"\bincreased\s+inventory\s+reserves\b", re.IGNORECASE),
    re.compile(
        r"\b(?:asset\s+impairment|inventory\s+write[-\s]down|tax\s+expense|effective\s+tax\s+rate)\s+"
        r"(?:rose|increased|fell|declined|dropped|improved|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:cash\s+balance|cash\s+reserves|cash\s+position)\s+"
        r"(?:rose|increased|grew|fell|declined|dropped|improved|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:net\s+debt|debt\s+load|total\s+debt)\s+(?:rose|increased|grew|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bleverage\s+(?:rose|increased|fell|declined|dropped|improved|worsened)\b", re.IGNORECASE),
    re.compile(r"\b(?:cash\s+burn|burn\s+rate)\s+(?:rose|increased|grew|fell|declined|dropped|improved|worsened)\b", re.IGNORECASE),
    re.compile(r"\b(?:cash\s+)?runway\s+(?:extended|lengthened|shortened|shrank)\b", re.IGNORECASE),
    re.compile(r"\bliquidity\s+(?:improved|worsened|tightened|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bworking\s+capital\s+(?:rose|increased|grew|fell|declined|dropped|improved|worsened)\b", re.IGNORECASE),
    re.compile(r"\bcurrent\s+ratio\s+(?:rose|increased|fell|declined|dropped|improved|worsened)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:inventory|receivables?|payables?)\s+turnover\s+"
        r"(?:improved|rose|increased|fell|declined|dropped|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bcash\s+conversion\s+cycle\s+(?:shortened|lengthened|improved|worsened)\b", re.IGNORECASE),
    re.compile(r"\bworking\s+capital\s+cycle\s+(?:shortened|lengthened|improved|worsened)\b", re.IGNORECASE),
    re.compile(r"\b(?:dso|dpo)\s+(?:rose|increased|fell|declined|dropped|improved|worsened)\b", re.IGNORECASE),
    re.compile(
        r"\bdays\s+(?:sales|payable|inventory)\s+outstanding\s+"
        r"(?:rose|increased|fell|declined|dropped|improved|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:inventory|receivable|payable)\s+days\s+(?:rose|increased|fell|declined|dropped|improved|worsened)\b", re.IGNORECASE),
    re.compile(
        r"\bdebt[-\s]to[-\s](?:equity|ebitda)(?:\s+ratio)?\s+"
        r"(?:rose|increased|fell|declined|dropped|improved|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\barpu\s+(?:increased|rose|improved|fell|declined|dropped|doubled|tripled)\b", re.IGNORECASE),
    re.compile(
        r"\baverage\s+revenue\s+per\s+user\s+(?:increased|rose|improved|fell|declined|dropped|doubled|tripled)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bmrr\s+(?:increased|rose|fell|declined|dropped|doubled|tripled)\b", re.IGNORECASE),
    re.compile(
        r"\bmonthly\s+recurring\s+revenue\s+(?:increased|rose|fell|declined|dropped|doubled|tripled)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\barr\s+(?:crossed|exceeded|reached|increased|rose|fell|declined|dropped|doubled|tripled)\b", re.IGNORECASE),
    re.compile(
        r"\bannual\s+recurring\s+revenue\s+(?:crossed|exceeded|reached|increased|rose|fell|declined|dropped|doubled|tripled)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bgmv\s+(?:increased|rose|fell|declined|dropped|doubled|tripled)\b", re.IGNORECASE),
    re.compile(
        r"\bgross\s+merchandise\s+value\s+(?:increased|rose|fell|declined|dropped|doubled|tripled)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\btake\s+rate\s+(?:improved|increased|rose|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\baov\s+(?:rose|increased|fell|declined|dropped|improved|worsened)\b", re.IGNORECASE),
    re.compile(
        r"\baverage\s+order\s+value\s+(?:rose|increased|fell|declined|dropped|improved|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:average\s+)?basket\s+size\s+(?:rose|increased|fell|declined|dropped|improved|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bcart\s+abandonment\s+rate\s+(?:rose|increased|fell|declined|dropped|improved|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bcheckout\s+conversion\s+(?:rose|increased|fell|declined|dropped|improved|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:same[-\s]store|comp|comparable)\s+sales\s+"
        r"(?:rose|increased|fell|declined|dropped|improved|worsened|doubled|tripled)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:store|foot)\s+traffic\s+(?:rose|increased|fell|declined|dropped|improved|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:channel\s+)?sell[-\s]through(?:\s+rate)?\s+"
        r"(?:rose|increased|fell|declined|dropped|improved|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bltv[\/-]cac\s+(?:improved|increased|rose|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(
        r"\bcustomer\s+acquisition\s+cost\s+(?:fell|declined|dropped|rose|increased)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bunit\s+economics\s+turned\s+positive\b", re.IGNORECASE),
    re.compile(r"\bcapex\s+(?:doubled|tripled|rose|increased|surged|spiked|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(
        r"\bcapital\s+(?:expenditure|spending)\s+"
        r"(?:doubled|tripled|rose|increased|surged|spiked|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:(?:ai\s+)?infrastructure|cloud)\s+spend(?:ing)?\s+"
        r"(?:doubled|tripled|rose|increased|surged|spiked|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:r&d|research\s+and\s+development)\s+spending\s+"
        r"(?:doubled|tripled|rose|increased|surged|spiked|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:marketing|procurement|data\s+center|investment)\s+budget\s+"
        r"(?:doubled|tripled|rose|increased|surged|spiked|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bopex\s+(?:doubled|tripled|rose|increased|surged|spiked|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(
        r"\boperating\s+expenses\s+(?:doubled|tripled|rose|increased|surged|spiked|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:component|raw\s+material|input|freight|shipping|logistics|energy|packaging)\s+costs?\s+"
        r"(?:doubled|tripled|rose|increased|surged|spiked|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:wafer|memory)\s+prices?\s+"
        r"(?:doubled|tripled|rose|increased|surged|spiked|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:bill\s+of\s+materials|bom)\s+costs?\s+"
        r"(?:rose|increased|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bcogs\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\b(?:raised|cut|lowered|hiked)\s+subscription\s+prices\b", re.IGNORECASE),
    re.compile(r"\bsubscription\s+pricing\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\b(?:monthly\s+fees|annual\s+plan\s+prices|seat\s+prices)\s+(?:rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\b(?:usage[-\s]based\s+pricing|metered\s+billing)\s+(?:launched|started|expanded|ended)\b", re.IGNORECASE),
    re.compile(r"\b(?:launched|introduced)\s+(?:usage[-\s]based\s+pricing|metered\s+billing|a\s+paid\s+tier)\b", re.IGNORECASE),
    re.compile(r"\bremoved\s+(?:the\s+)?free\s+plan\b", re.IGNORECASE),
    re.compile(r"\b(?:raised|lowered|cut|hiked)\s+platform\s+fees\b", re.IGNORECASE),
    re.compile(r"\bcommission\s+rate\s+(?:rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bdiscounting\s+(?:rose|increased|expanded|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\basp\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(
        r"\baverage\s+selling\s+prices?\s+(?:rose|increased|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:unit|list|wholesale|resale)\s+prices?\s+"
        r"(?:rose|increased|spiked|surged|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?<!average\s)\bselling\s+prices?\s+(?:rose|increased|spiked|surged|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bdiscount\s+rates?\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\brebates?\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bprice\s+premium\s+(?:widened|narrowed|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bprice\s+gap\s+(?:widened|narrowed|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\broas\s+(?:improved|increased|rose|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\breturn\s+on\s+ad\s+spend\s+(?:improved|increased|rose|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bctr\s+(?:improved|increased|rose|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bclick[-\s]through\s+rate\s+(?:improved|increased|rose|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bcpc\s+(?:fell|declined|dropped|rose|increased)\b", re.IGNORECASE),
    re.compile(r"\bcost\s+per\s+click\s+(?:fell|declined|dropped|rose|increased)\b", re.IGNORECASE),
    re.compile(r"\bcpm\s+(?:fell|declined|dropped|rose|increased)\b", re.IGNORECASE),
    re.compile(r"\bcost\s+per\s+mille\s+(?:fell|declined|dropped|rose|increased)\b", re.IGNORECASE),
    re.compile(r"\bad\s+revenue\s+(?:increased|rose|fell|declined|dropped|doubled|tripled)\b", re.IGNORECASE),
    re.compile(
        r"\badvertising\s+revenue\s+(?:increased|rose|fell|declined|dropped|doubled|tripled)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?<!on\s)\bad\s+spend\s+(?:fell|declined|dropped|rose|increased)\b", re.IGNORECASE),
    re.compile(r"\bcampaign\s+impressions\s+(?:surged|spiked|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\b(?:gained|lost)\s+market\s+share\b", re.IGNORECASE),
    re.compile(r"\bmarket\s+share\s+(?:doubled|tripled|rose|fell|increased|declined)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:install(?:ed)?|customer|user)\s+base\s+"
        r"(?:grew|rose|increased|expanded|doubled|tripled|fell|declined|dropped|shrank)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\battach\s+rates?\s+(?:improved|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:market|category|household|enterprise)\s+penetration\s+"
        r"(?:improved|rose|increased|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bshare\s+of\s+wallet\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bwallet\s+share\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\b(?:category|segment)\s+share\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bdownloads?\s+(?:surged|spiked|rose|increased|doubled|tripled)\b", re.IGNORECASE),
    re.compile(r"\bcrossed\s+(?:one|two|three|four|five|ten)\s+million\s+downloads\b", re.IGNORECASE),
    re.compile(r"\b(?:monthly|daily)\s+active\s+users?\s+(?:rose|fell|increased|declined|doubled|tripled)\b", re.IGNORECASE),
    re.compile(r"\bsubscribers?\s+(?:doubled|tripled|rose|fell|increased|declined)\b", re.IGNORECASE),
    re.compile(r"\breached\s+(?:one|two|three|four|five|ten)\s+million\s+subscribers\b", re.IGNORECASE),
    re.compile(r"\bconversion\s+rate\s+(?:improved|rose|increased|doubled|tripled)\b", re.IGNORECASE),
    re.compile(r"\bengagement\s+rate\s+hit\s+(?:a\s+)?record\b", re.IGNORECASE),
    re.compile(r"\bapp\s+installs?\s+(?:surged|spiked|rose|increased|doubled|tripled)\b", re.IGNORECASE),
    re.compile(r"\borganic\s+traffic\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:website|web)\s+traffic\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bpage\s+views?\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bunique\s+visitors?\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bbounce\s+rate\s+(?:fell|declined|dropped|rose|increased)\b", re.IGNORECASE),
    re.compile(
        r"\baverage\s+session\s+duration\s+(?:rose|increased|improved|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:search|seo)\s+ranking\s+(?:improved|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bdomain\s+authority\s+(?:improved|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\breferral\s+traffic\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bnewsletter\s+signups?\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bgithub\s+stars?\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bgithub\s+forks?\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\brepository\s+stars?\s+(?:crossed|exceeded|reached|surged|rose|increased|doubled|tripled)\b", re.IGNORECASE),
    re.compile(r"(?<!external\s)\bcontributors?\s+(?:grew|surged|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bexternal\s+contributors?\s+(?:grew|surged|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bpull\s+requests?\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bapi\s+calls?\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bapi\s+usage\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bsdk\s+adoption\s+(?:grew|surged|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bdeveloper\s+signups?\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bdocker\s+pulls?\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bcontainer\s+pulls?\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bwon\s+(?:an?\s+)?(?:industry\s+|innovation\s+|product\s+)?award\b", re.IGNORECASE),
    re.compile(r"\breceived\s+(?:an?\s+)?(?:industry\s+|innovation\s+|product\s+)?award\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were)\s+named\s+product\s+of\s+the\s+year\b", re.IGNORECASE),
    re.compile(r"\bearned\s+(?:an?\s+)?(?:editor'?s\s+choice|five[-\s]star\s+rating)\b", re.IGNORECASE),
    re.compile(r"\bapp\s+rating\s+(?:rose|increased|improved|fell|declined)\b", re.IGNORECASE),
    re.compile(r"\breviews?\s+(?:rose|increased|improved|fell|declined)\b", re.IGNORECASE),
    re.compile(r"\breached\s+\d+(?:\.\d+)?\s+stars?\b", re.IGNORECASE),
    re.compile(r"\btopped\s+(?:the\s+)?app\s+store\s+rankings?\b", re.IGNORECASE),
    re.compile(r"\bbecame\s+(?:the\s+)?top[-\s]rated\s+app\b", re.IGNORECASE),
    re.compile(r"\b(?:trustpilot|g2)\s+(?:score|rating)\s+(?:rose|increased|improved|fell|declined)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:signed|announced|formed|entered)\s+(?:a\s+)?"
        r"(?:major\s+|new\s+|strategic\s+)?(?:partnership|deal|contract|agreement|alliance)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:entered|formed|launched)\s+(?:a\s+|an\s+)?"
        r"(?:strategic\s+)?joint\s+venture\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:announced|formed|started|expanded)\s+(?:a\s+|an\s+)?"
        r"(?:strategic\s+)?collaboration\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bpartnered\s+with\s+(?:a\s+)?(?:top\s+|major\s+|new\s+|strategic\s+)?"
        r"(?:cloud\s+provider|customer|partner|supplier|vendor|hyperscaler|chipmaker|automaker|retailer|bank|company)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:secured|landed|won|captured)\s+(?:a\s+)?"
        r"(?:major\s+|new\s+|large\s+|strategic\s+|marquee\s+)?(?:deal|contract|order|customer|account)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsigned\s+(?:a\s+|an\s+)?"
        r"(?:(?:major|new|large|strategic|marquee|enterprise)\s+){0,3}(?:customer|account)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\badded\s+(?:a\s+)?(?:major\s+|new\s+|large\s+|strategic\s+|marquee\s+)?customer\b", re.IGNORECASE),
    re.compile(r"\blocked\s+in\s+(?:a\s+)?(?:supply\s+)?agreement\b", re.IGNORECASE),
    re.compile(r"\b(?:net\s+)?bookings\s+(?:doubled|tripled|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bbillings\s+(?:doubled|tripled|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:remaining\s+performance\s+obligations|rpo)\s+"
        r"(?:doubled|tripled|rose|increased|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bpre[-\s]?order\s+volume\s+(?:doubled|tripled|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bpurchase\s+orders?\s+(?:doubled|tripled|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bsales\s+pipeline\s+(?:grew|expanded|increased|rose|fell|declined|dropped|shrank)\b", re.IGNORECASE),
    re.compile(r"\bwon\s+(?:a\s+|an\s+)?rfp\b", re.IGNORECASE),
    re.compile(
        r"\b(?:signed|entered|secured|announced)\s+(?:a\s+|an\s+)?"
        r"(?:data\s+licensing|technology\s+licensing|licensing|reseller|"
        r"exclusive\s+distribution|distribution|data\s+sharing|oem)\s+agreement\b",
        re.IGNORECASE,
    ),
    re.compile(r"\blicensed\s+(?:its\s+|the\s+)?technology\s+to\s+(?:a\s+)?(?:partner|customer|company)\b", re.IGNORECASE),
    re.compile(r"\bsigned\s+(?:a\s+|an\s+)?(?:memorandum\s+of\s+understanding|mou)\b", re.IGNORECASE),
    re.compile(r"\binked\s+(?:a\s+)?(?:major\s+|new\s+|strategic\s+)?(?:deal|partnership|contract|agreement|alliance)\b", re.IGNORECASE),
    re.compile(r"\bbecame\s+(?:an?\s+)?(?:oem\s+partner|exclusive\s+supplier)\b", re.IGNORECASE),
    re.compile(r"\bexpanded\s+(?:its\s+|the\s+)?customer\s+base\b", re.IGNORECASE),
    re.compile(
        r"\b(?:chips?|platform|systems?|technology)\s+(?:was|were)\s+adopted\s+by\s+"
        r"(?:a\s+)?(?:major\s+|top\s+|enterprise\s+)?"
        r"(?:cloud\s+provider|hyperscaler|customer|enterprise|company)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bhyperscaler\s+deployed\s+[a-z0-9&.'-]+\s+chips\b", re.IGNORECASE),
    re.compile(r"\bbecame\s+(?:the\s+)?default\s+supplier\b", re.IGNORECASE),
    re.compile(r"\bwon\s+(?:a\s+)?production\s+deployment\b", re.IGNORECASE),
    re.compile(r"\bmoved\s+from\s+pilot\s+to\s+production\b", re.IGNORECASE),
    re.compile(r"\bcompleted\s+(?:a\s+)?customer\s+rollout\b", re.IGNORECASE),
    re.compile(r"\bentered\s+commercial\s+deployment\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were)\s+installed\s+in\s+enterprise\s+data\s+centers\b", re.IGNORECASE),
    re.compile(r"\bqualified\s+as\s+(?:a\s+)?preferred\s+supplier\b", re.IGNORECASE),
    re.compile(r"\bintegrated\s+with\s+(?:a\s+)?hyperscaler\s+platform\b", re.IGNORECASE),
    re.compile(r"\bpassed\s+customer\s+acceptance\s+testing\b", re.IGNORECASE),
    re.compile(r"\bsecured\s+enterprise\s+adoption\b", re.IGNORECASE),
    re.compile(
        r"\b(?:won|secured|landed|signed)\s+(?:a\s+|an\s+)?"
        r"(?:pentagon|dod|defense|military|army|navy|air\s+force|government|federal|public[-\s]sector)\s+"
        r"(?:ai\s+)?(?:contract|deal|agreement|tender)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\breceived\s+(?:a\s+|an\s+)?(?:federal\s+grant|government\s+funding)\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were)\s+selected\s+for\s+(?:a\s+|an\s+)?government\s+program\b", re.IGNORECASE),
    re.compile(r"\bjoined\s+(?:a\s+|an\s+)?national\s+security\s+project\b", re.IGNORECASE),
    re.compile(
        r"\b(?:was|were)\s+approved\s+for\s+(?:a\s+|an\s+)?defense\s+procurement\s+program\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:army|navy|air\s+force|nato|pentagon|dod)\s+"
        r"(?:selected|adopted)\s+(?:its\s+)?(?:chips?|platform|system|systems|technology)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:appointed|named|hired|promoted)\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?"
        r"(?:ceo|cfo|coo|chief\s+executive|chief\s+financial\s+officer|"
        r"chief\s+operating\s+officer|finance\s+chief|president|board\s+member|director)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:replaced|ousted)\s+(?:its\s+|the\s+)?"
        r"(?:ceo|cfo|coo|chief\s+executive|chief\s+financial\s+officer|"
        r"chief\s+operating\s+officer|finance\s+chief|president)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:ceo|cfo|coo|chief\s+executive|chief\s+financial\s+officer|"
        r"chief\s+operating\s+officer|finance\s+chief|president|founder)\s+"
        r"(?:resigned|departed|stepped\s+down|stepped\s+aside)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bboard\s+reshuffled\s+leadership\b", re.IGNORECASE),
    re.compile(r"\badded\s+(?:a\s+|an\s+)?(?:new\s+)?board\s+member\b", re.IGNORECASE),
    re.compile(r"\bsuffered\s+(?:a\s+)?data\s+breach\b", re.IGNORECASE),
    re.compile(r"\bdisclosed\s+(?:a\s+)?data\s+breach\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were|got)\s+hacked\b", re.IGNORECASE),
    re.compile(r"\b(?:leaked|exposed)\s+(?:customer|user|personal|private)\s+data\b", re.IGNORECASE),
    re.compile(r"\b(?:customer|user|personal|private)\s+data\s+leaked\b", re.IGNORECASE),
    re.compile(r"\buser\s+records\s+(?:were|was)\s+exposed\b", re.IGNORECASE),
    re.compile(r"\b(?:credentials|passwords)\s+(?:were|was)\s+(?:stolen|leaked)\b", re.IGNORECASE),
    re.compile(r"\bpasswords\s+leaked\s+online\b", re.IGNORECASE),
    re.compile(r"\bconfirmed\s+(?:a\s+)?security\s+incident\b", re.IGNORECASE),
    re.compile(
        r"\b(?:fixed|patched)\s+(?:a\s+|an\s+)?(?:zero[-\s]?day|critical)\s+vulnerabilit(?:y|ies)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bachieved\s+soc\s*2\s+compliance\b", re.IGNORECASE),
    re.compile(r"\breceived\s+iso\s*27001\s+certification\b", re.IGNORECASE),
    re.compile(r"\b(?:earned|received)\s+fedramp\s+authorization\b", re.IGNORECASE),
    re.compile(r"\bbecame\s+hipaa\s+compliant\b", re.IGNORECASE),
    re.compile(r"\bmet\s+gdpr\s+requirements\b", re.IGNORECASE),
    re.compile(r"\bpassed\s+(?:a\s+)?(?:security|compliance)\s+audit\b", re.IGNORECASE),
    re.compile(r"\bcompleted\s+(?:a\s+)?penetration\s+test\b", re.IGNORECASE),
    re.compile(r"\bresolved\s+all\s+vulnerabilities\b", re.IGNORECASE),
    re.compile(r"\bachieved\s+zero\s+critical\s+vulnerabilities\b", re.IGNORECASE),
    re.compile(r"\breceived\s+fips\s+certification\b", re.IGNORECASE),
    re.compile(r"\bearned\s+(?:a\s+)?security\s+certification\b", re.IGNORECASE),
    re.compile(r"\battackers\s+stole\s+source\s+code\b", re.IGNORECASE),
    re.compile(r"\bsource\s+code\s+(?:was|were)\s+(?:stolen|leaked)\b", re.IGNORECASE),
    re.compile(r"\bmalware\s+infected\s+(?:systems?|devices?|servers?|networks?)\b", re.IGNORECASE),
    re.compile(r"\bphishing\s+campaign\s+targeted\s+(?:users?|customers?|employees?)\b", re.IGNORECASE),
    re.compile(r"\bexploited\s+(?:a\s+|an\s+)?zero[-\s]?day\s+vulnerabilit(?:y|ies)\b", re.IGNORECASE),
    re.compile(r"\bcritical\s+vulnerabilit(?:y|ies)\s+(?:was|were)\s+exploited\b", re.IGNORECASE),
    re.compile(r"\bprivacy\s+violation\s+exposed\s+(?:users?|customers?|personal\s+data|private\s+data)\b", re.IGNORECASE),
    re.compile(r"\bfaced\s+(?:a\s+)?ransomware\s+attack\b", re.IGNORECASE),
    re.compile(r"\boutage\s+affected\s+(?:users?|customers?|services?|platforms?)\b", re.IGNORECASE),
    re.compile(r"\b(?:service|app|platform|site|api)\s+went\s+(?:offline|down)\b", re.IGNORECASE),
    re.compile(r"\bissued\s+refunds?\b", re.IGNORECASE),
    re.compile(r"\boffered\s+compensation\s+to\s+(?:users?|customers?|subscribers?)\b", re.IGNORECASE),
    re.compile(r"\bgave\s+service\s+credits?\b", re.IGNORECASE),
    re.compile(r"\bcustomer\s+complaints\s+(?:surged|spiked|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bcomplaint\s+volume\s+(?:surged|spiked|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bnps\s+(?:improved|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bnet\s+promoter\s+score\s+(?:improved|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bcsat\s+(?:improved|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bcustomer\s+satisfaction\s+(?:improved|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\buser\s+sentiment\s+(?:turned\s+positive|improved|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bbrand\s+trust\s+(?:improved|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bsupport\s+tickets?\s+(?:fell|dropped|declined|rose|increased|surged|spiked)\b", re.IGNORECASE),
    re.compile(r"\bbug\s+reports?\s+(?:fell|dropped|declined|rose|increased|surged|spiked)\b", re.IGNORECASE),
    re.compile(r"\bcrash\s+rates?\s+(?:fell|dropped|declined|rose|increased|surged|spiked)\b", re.IGNORECASE),
    re.compile(r"\bcrashes\s+(?:fell|dropped|declined|rose|increased|surged|spiked)\b", re.IGNORECASE),
    re.compile(r"\brefund\s+rates?\s+(?:rose|increased|fell|declined|dropped|improved|worsened)\b", re.IGNORECASE),
    re.compile(r"\bchargeback\s+rates?\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\b(?:ticket|support)\s+backlog\s+(?:grew|rose|increased|fell|declined|dropped|shrank)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:first\s+response|response|resolution)\s+times?\s+"
        r"(?:improved|rose|increased|fell|declined|dropped|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\baverage\s+handle\s+time\s+(?:improved|rose|increased|fell|declined|dropped|worsened)\b", re.IGNORECASE),
    re.compile(r"\bsla\s+breach\s+rates?\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bservice\s+credit\s+requests?\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\buptime\s+improved\b", re.IGNORECASE),
    re.compile(r"\bsla\s+compliance\s+improved\b", re.IGNORECASE),
    re.compile(r"\busers?\s+canceled\s+subscriptions?\b", re.IGNORECASE),
    re.compile(r"\bsubscription\s+cancellations?\s+(?:surged|spiked|rose|increased)\b", re.IGNORECASE),
    re.compile(r"(?<!customer\s)(?<!user\s)(?<!subscriber\s)\bchurn\s+(?:surged|spiked|rose|increased)\b", re.IGNORECASE),
    re.compile(r"(?<!customer\s)(?<!user\s)(?<!subscriber\s)\bchurn\s+(?:fell|dropped|declined)\b", re.IGNORECASE),
    re.compile(r"\b(?:customer|user|subscriber)\s+churn\s+(?:surged|spiked|rose|increased|fell|dropped|declined)\b", re.IGNORECASE),
    re.compile(r"(?<!revenue\s)\b(?:customer|user|subscriber)?\s*retention\s+(?:fell|dropped|declined)\b", re.IGNORECASE),
    re.compile(
        r"(?<!revenue\s)\b(?:customer\s+|user\s+|subscriber\s+)?retention\s+(?:improved|rose|increased|doubled|tripled)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:net\s+revenue\s+retention|gross\s+revenue\s+retention|nrr|grr)\s+"
        r"(?:improved|rose|increased|doubled|tripled|fell|dropped|declined)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:paying|paid)\s+(?:users?|customers?)\s+(?:rose|increased|doubled|tripled|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:free[-\s]to[-\s]paid|trial|paid)\s+conversion\s+(?:improved|rose|increased|doubled|tripled|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bwarranty\s+claims\s+(?:surged|spiked|rose|increased)\b", re.IGNORECASE),
    re.compile(r"\b(?:product\s+returns|return\s+rates)\s+(?:surged|spiked|rose|increased)\b", re.IGNORECASE),
    re.compile(r"\bmissed\s+(?:its\s+)?uptime\s+sla\b", re.IGNORECASE),
    re.compile(r"\bdowntime\s+triggered\s+refunds?\b", re.IGNORECASE),
    re.compile(r"\binsurance\s+payout\s+covered\b", re.IGNORECASE),
    re.compile(r"\binsurer\s+denied\s+coverage\b", re.IGNORECASE),
    re.compile(r"\bpremiums?\s+(?:increased|rose|spiked|surged)\b", re.IGNORECASE),
    re.compile(r"\bliability\s+coverage\s+(?:was|were)\s+exhausted\b", re.IGNORECASE),
    re.compile(r"\bpaid\s+damages\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were)\s+ordered\s+to\s+pay\s+damages\b", re.IGNORECASE),
    re.compile(r"\breimbursed\s+customers\b", re.IGNORECASE),
    re.compile(r"\bextended\s+warranties\b", re.IGNORECASE),
    re.compile(r"\boffered\s+recall\s+reimbursements?\b", re.IGNORECASE),
    re.compile(r"\binsurance\s+claim\s+(?:was|were)\s+denied\b", re.IGNORECASE),
    re.compile(r"\bapp\s+(?:was|were)\s+removed\s+from\s+(?:the\s+)?app\s+store\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were)\s+banned\s+from\s+google\s+play\b", re.IGNORECASE),
    re.compile(r"\baccount\s+(?:was|were)\s+suspended\b", re.IGNORECASE),
    re.compile(r"\bads?\s+(?:was|were)\s+banned\b", re.IGNORECASE),
    re.compile(r"\bapi\s+access\s+(?:was|were)\s+revoked\b", re.IGNORECASE),
    re.compile(r"\bdeveloper\s+account\s+(?:was|were)\s+terminated\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were)\s+demonetized\b", re.IGNORECASE),
    re.compile(r"\bposts?\s+(?:was|were)\s+removed\b", re.IGNORECASE),
    re.compile(r"\bcontent\s+(?:was|were)\s+flagged\s+as\s+misinformation\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were)\s+shadowbanned\b", re.IGNORECASE),
    re.compile(r"\blost\s+platform\s+access\b", re.IGNORECASE),
    re.compile(r"\bchannel\s+(?:was|were)\s+taken\s+down\b", re.IGNORECASE),
    re.compile(
        r"\b(?:acquired|bought)\s+(?:a\s+|an\s+|the\s+)?"
        r"(?:startup|company|rival|competitor|business|unit|division|stake|asset|assets)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:announced|completed|closed|finalized)\s+(?:a\s+|an\s+|the\s+)?"
        r"(?:merger|acquisition|takeover|buyout|spinoff|spin-off)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:raised|closed|secured)\s+(?:a\s+|an\s+)?(?:funding|financing)(?:\s+round)?\b", re.IGNORECASE),
    re.compile(r"\bclosed\s+(?:a\s+|an\s+)?(?:seed|series\s+[a-e]|funding|financing)\s+round\b", re.IGNORECASE),
    re.compile(r"\bfiled(?:\s+confidentially)?\s+for\s+(?:an?\s+)?ipo\b", re.IGNORECASE),
    re.compile(r"\b(?:launched|priced|delayed|completed)\s+(?:its\s+|an?\s+)?ipo\b", re.IGNORECASE),
    re.compile(r"\bwent\s+public\b", re.IGNORECASE),
    re.compile(r"\blisted\s+on\s+(?:nasdaq|nyse|a\s+stock\s+exchange|the\s+stock\s+exchange)\b", re.IGNORECASE),
    re.compile(r"\bdebuted\s+on\s+(?:the\s+)?(?:nasdaq|nyse|stock\s+exchange)\b", re.IGNORECASE),
    re.compile(r"\bcompleted\s+(?:a\s+|an\s+)?spac\s+merger\b", re.IGNORECASE),
    re.compile(r"\bsecured\s+unicorn\s+valuation\b", re.IGNORECASE),
    re.compile(r"\bvaluation\s+(?:doubled|tripled|rose|fell|increased|declined)\b", re.IGNORECASE),
    re.compile(r"\blaunched\s+(?:a\s+|an\s+)?secondary\s+offering\b", re.IGNORECASE),
    re.compile(r"\b(?:sold|offloaded)\s+(?:a\s+|an\s+)?(?:minority\s+|majority\s+)?(?:stake|unit|division|business)\b", re.IGNORECASE),
    re.compile(r"\bspun\s+off\s+(?:a\s+|an\s+|the\s+)?(?:unit|division|business|subsidiary)\b", re.IGNORECASE),
    re.compile(r"\blaunched\s+(?:a\s+|an\s+)?(?:share\s+)?buyback\b", re.IGNORECASE),
    re.compile(
        r"\b(?:authorized|approved|announced|launched|expanded|increased|raised|cut|reduced|suspended)\s+"
        r"(?:a\s+|an\s+|the\s+|its\s+)?(?:share\s+repurchase|stock\s+repurchase|share\s+buyback|buyback)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bdeclared\s+(?:a\s+|an\s+)?(?:quarterly\s+|special\s+)?dividend\b", re.IGNORECASE),
    re.compile(r"\b(?:increased|raised|cut|reduced|suspended|resumed)\s+(?:its\s+|the\s+)?dividend\b", re.IGNORECASE),
    re.compile(r"\b(?:announced|completed|approved)\s+(?:a\s+|an\s+)?(?:reverse\s+)?(?:stock|share)\s+split\b", re.IGNORECASE),
    re.compile(r"\b(?:issued|sold)\s+(?:new\s+)?shares\b", re.IGNORECASE),
    re.compile(r"\bfiled\s+(?:a\s+|an\s+)?shelf\s+offering\b", re.IGNORECASE),
    re.compile(r"\blaunched\s+(?:a\s+|an\s+)?(?:at[-\s]the[-\s]market|atm)\s+offering\b", re.IGNORECASE),
    re.compile(r"\braised\s+capital\s+through\s+(?:a\s+)?share\s+sale\b", re.IGNORECASE),
    re.compile(r"\bcompleted\s+(?:a\s+|an\s+)?private\s+placement\b", re.IGNORECASE),
    re.compile(r"\bshipments?\s+(?:were|was|are|is)\s+seized\s+by\s+customs\b", re.IGNORECASE),
    re.compile(r"\bcustoms\s+seized\s+[a-z0-9&.'-]+\s+(?:chips|shipments?|cargo|goods)\b", re.IGNORECASE),
    re.compile(r"\bshipments?\s+(?:were|was|are|is)\s+blocked\s+at\s+customs\b", re.IGNORECASE),
    re.compile(r"\bcargo\s+(?:was|were|is|are)\s+detained\s+at\s+(?:the\s+)?port\b", re.IGNORECASE),
    re.compile(r"\bsupplier\s+strike\s+disrupted\s+production\b", re.IGNORECASE),
    re.compile(r"\bport\s+delays\s+halted\s+deliveries\b", re.IGNORECASE),
    re.compile(r"\bsupply\s+chain\s+collapsed\b", re.IGNORECASE),
    re.compile(r"\binventory\s+stockout\s+hit\s+customers\b", re.IGNORECASE),
    re.compile(r"\b(?:order\s+)?fill\s+rate\s+(?:improved|rose|increased|fell|declined|dropped|worsened)\b", re.IGNORECASE),
    re.compile(r"\b(?:on[-\s]time\s+delivery|otif|delivery\s+performance)\s+(?:improved|rose|increased|fell|declined|dropped|worsened)\b", re.IGNORECASE),
    re.compile(r"\blate\s+deliveries\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\b(?:shipping|freight)\s+delays?\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\b(?:order\s+)?fulfillment\s+(?:improved|rose|increased|fell|declined|dropped|worsened)\b", re.IGNORECASE),
    re.compile(r"\bfulfillment\s+rate\s+(?:improved|rose|increased|fell|declined|dropped|worsened)\b", re.IGNORECASE),
    re.compile(r"\bstock[-\s]?outs?\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bbackorders?\s+(?:rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bservice\s+levels?\s+(?:improved|rose|increased|fell|declined|dropped|worsened)\b", re.IGNORECASE),
    re.compile(r"\bcomponent\s+shortage\s+forced\s+production\s+cuts\b", re.IGNORECASE),
    re.compile(r"\bimport\s+ban\s+blocked\s+chips\b", re.IGNORECASE),
    re.compile(r"\bsmuggling\s+network\s+shipped\s+chips\b", re.IGNORECASE),
    re.compile(r"\bgray[-\s]market\s+shipments\s+surged\b", re.IGNORECASE),
    re.compile(
        r"\b(?:launched|unveiled|released|debuted|introduced|shipped)\s+(?:a\s+|an\s+|the\s+)?"
        r"(?:new\s+|next-gen\s+|next\s+generation\s+)?(?:ai\s+)?"
        r"(?:chip|gpu|processor|model|ai\s+model|platform|product|service|feature|tool|app|device|system)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\brolled\s+out\s+(?:a\s+|an\s+|the\s+)?(?:new\s+|next-gen\s+|next\s+generation\s+)?"
        r"(?:chip|processor|model|ai\s+model|platform|product|service|feature|tool|app|device|system)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bopened\s+preorders\b", re.IGNORECASE),
    re.compile(r"\bstarted\s+beta\s+testing\b", re.IGNORECASE),
    re.compile(r"\bmade\s+(?:the\s+)?product\s+generally\s+available\b", re.IGNORECASE),
    re.compile(r"\bstarted\s+mass\s+production\b", re.IGNORECASE),
    re.compile(r"\bdelayed\s+(?:a\s+|the\s+)?product\s+launch\b", re.IGNORECASE),
    re.compile(r"\b(?:cut|raised|hiked|lowered)\s+(?:gpu\s+|chip\s+|device\s+|product\s+)?prices\b", re.IGNORECASE),
    re.compile(r"\bsold\s+out\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?(?:ai\s+)?(?:chip|gpu|device|product|model)\b", re.IGNORECASE),
    re.compile(r"\bshipped\s+(?:the\s+)?first\s+units\b", re.IGNORECASE),
    re.compile(r"\bhalted\s+shipments\b", re.IGNORECASE),
    re.compile(r"\bexpanded\s+production\s+capacity\b", re.IGNORECASE),
    re.compile(r"\breported\s+supply\s+shortages\b", re.IGNORECASE),
    re.compile(
        r"\bopened\s+(?:a\s+|an\s+|new\s+)?(?:(?:flagship\s+)?stores?|retail\s+locations?|showrooms?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bstore\s+count\s+(?:doubled|tripled|rose|increased|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bexpanded\s+(?:retail\s+)?footprint\b", re.IGNORECASE),
    re.compile(
        r"\bexpanded\s+(?:into|presence\s+in)\s+[a-z][a-z0-9&.'-]*"
        r"(?:\s+(?!(?:after|amid|as|following|on|with|because|when)\b)[a-z][a-z0-9&.'-]*){0,4}"
        r"(?=\s+(?:after|amid|as|following|on|with|because|when)\b|[.,;:!?]|$)",
        re.IGNORECASE,
    ),
    re.compile(r"\bentered\s+(?:the\s+)?[a-z][a-z0-9&.'-]*(?:\s+[a-z][a-z0-9&.'-]*){0,3}\s+market\b", re.IGNORECASE),
    re.compile(
        r"\blaunched\s+in\s+[a-z][a-z0-9&.'-]*"
        r"(?:\s+(?!(?:after|amid|as|following|on|with|because|when)\b)[a-z][a-z0-9&.'-]*){0,3}"
        r"(?=\s+(?:after|amid|as|following|on|with|because|when)\b|[.,;:!?]|$)",
        re.IGNORECASE,
    ),
    re.compile(r"\badded\s+distribution\s+centers?\b", re.IGNORECASE),
    re.compile(r"\bopened\s+(?:new\s+)?warehouses?\b", re.IGNORECASE),
    re.compile(r"\b(?:began|started|localized)\s+local\s+production\b", re.IGNORECASE),
    re.compile(r"\bopened\s+(?:a\s+|an\s+)?regional\s+headquarters\b", re.IGNORECASE),
    re.compile(r"\blead\s+times?\s+(?:doubled|tripled|rose|increased|stretched|lengthened)\b", re.IGNORECASE),
    re.compile(r"\bdelivery\s+times?\s+(?:doubled|tripled|rose|increased|stretched|lengthened)\b", re.IGNORECASE),
    re.compile(r"\ballocation\s+(?:tightened|eased|opened|closed)\b", re.IGNORECASE),
    re.compile(r"\binventory\s+(?:was|were)\s+depleted\b", re.IGNORECASE),
    re.compile(r"\binventory\s+levels?\s+(?:fell|dropped|declined|rose|increased)\b", re.IGNORECASE),
    re.compile(r"\bchannel\s+inventory\s+dried\s+up\b", re.IGNORECASE),
    re.compile(r"\bproduct\s+availability\s+(?:improved|worsened|tightened|expanded)\b", re.IGNORECASE),
    re.compile(r"\bwaitlists?\s+(?:grew|expanded|increased|shrank|fell)\b", re.IGNORECASE),
    re.compile(r"\border\s+book\s+(?:filled|grew|expanded|increased)\b", re.IGNORECASE),
    re.compile(r"\bbook[-\s]to[-\s]bill\s+ratio\s+(?:rose|increased|fell|declined)\b", re.IGNORECASE),
    re.compile(r"\bannounced\s+layoffs\b", re.IGNORECASE),
    re.compile(r"\bcut\s+jobs\b", re.IGNORECASE),
    re.compile(r"\blaid\s+off\s+(?:employees?|workers?|staff)\b", re.IGNORECASE),
    re.compile(r"\bslashed\s+(?:its\s+|the\s+)?workforce\b", re.IGNORECASE),
    re.compile(r"\breduced\s+headcount\b", re.IGNORECASE),
    re.compile(r"\bfroze\s+hiring\b", re.IGNORECASE),
    re.compile(r"\brescinded\s+job\s+offers\b", re.IGNORECASE),
    re.compile(r"\bclosed\s+offices?\b", re.IGNORECASE),
    re.compile(r"\bhired\s+(?:new\s+)?(?:engineers|workers|staff|employees)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:headcount|workforce|employee\s+count|staffing\s+levels?)\s+"
        r"(?:grew|rose|increased|expanded|doubled|tripled|fell|declined|dropped|shrank)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bhiring\s+(?:increased|rose|grew|slowed|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bjob\s+openings?\s+(?:increased|rose|grew|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(
        r"\battrition\s+(?:rose|increased|fell|declined|dropped)\b|"
        r"(?<!inventory\s)(?<!receivable\s)(?<!receivables\s)(?<!payable\s)(?<!payables\s)"
        r"\bturnover\s+(?:rose|increased|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bworkers?\s+went\s+on\s+strike\b", re.IGNORECASE),
    re.compile(r"\bemployees?\s+voted\s+to\s+strike\b", re.IGNORECASE),
    re.compile(r"\bemployees?\s+staged\s+(?:a\s+)?walkout\b", re.IGNORECASE),
    re.compile(r"\bworkers?\s+voted\s+to\s+unionize\b", re.IGNORECASE),
    re.compile(r"\bunion\s+filed\s+(?:a\s+)?complaint\b", re.IGNORECASE),
    re.compile(r"\blabor\s+board\s+(?:opened|launched)\s+(?:a\s+|an\s+)?investigation\b", re.IGNORECASE),
    re.compile(r"\bosha\s+(?:opened|launched)\s+(?:a\s+|an\s+)?investigation\b", re.IGNORECASE),
    re.compile(r"\bfaced\s+wage\s+theft\s+claims\b", re.IGNORECASE),
    re.compile(r"\bcut\s+worker\s+pay\b", re.IGNORECASE),
    re.compile(r"\bemployees?\s+alleged\s+(?:harassment|discrimination)\b", re.IGNORECASE),
    re.compile(r"\bworkplace\s+injur(?:y|ies)\s+(?:was|were)\s+reported\b", re.IGNORECASE),
    re.compile(r"\bworkers?\s+rejected\s+(?:a\s+|the\s+)?contract\b", re.IGNORECASE),
    re.compile(r"\bunion\s+approved\s+(?:a\s+|the\s+)?contract\b", re.IGNORECASE),
    re.compile(r"\b(?:reached|signed)\s+(?:a\s+|an\s+)?labor\s+agreement\b", re.IGNORECASE),
    re.compile(r"\bended\s+(?:a\s+|the\s+)?worker\s+strike\b", re.IGNORECASE),
    re.compile(r"\b(?:union\s+|labor\s+)?contract\s+talks\s+collapsed\b", re.IGNORECASE),
    re.compile(r"\bopened\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?(?:factory|plant|facility|site)\b", re.IGNORECASE),
    re.compile(r"\bclosed\s+(?:a\s+|an\s+|the\s+)?(?:factory|plant|facility|site)\b", re.IGNORECASE),
    re.compile(r"\b(?:paused|halted|stopped|resumed|restarted|shifted)\s+production\b", re.IGNORECASE),
    re.compile(r"\bexpanded\s+(?:manufacturing|production|capacity|operations)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:yield\s+rate|production\s+yield|manufacturing\s+yield|chip\s+yields?)\s+"
        r"(?:improved|rose|increased|fell|declined|dropped|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:defect|failure|scrap)\s+rates?\s+"
        r"(?:rose|increased|fell|declined|dropped|improved|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:factory|fab|plant|line|capacity)\s+utili[sz]ation\s+"
        r"(?:rose|increased|fell|declined|dropped|improved|worsened)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:production|factory|manufacturing|fab)\s+output\s+"
        r"(?:doubled|tripled|rose|increased|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bline\s+efficiency\s+(?:improved|rose|increased|fell|declined|dropped|worsened)\b", re.IGNORECASE),
    re.compile(r"\bequipment\s+uptime\s+(?:rose|increased|improved|fell|declined|dropped|worsened)\b", re.IGNORECASE),
    re.compile(r"\bopened\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?data\s+center\b", re.IGNORECASE),
    re.compile(r"\bbroke\s+ground\s+on\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?data\s+center\b", re.IGNORECASE),
    re.compile(r"\bstarted\s+construction\s+of\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?facility\b", re.IGNORECASE),
    re.compile(r"\bleased\s+data\s+center\s+capacity\b", re.IGNORECASE),
    re.compile(r"\bsecured\s+power\s+capacity\b", re.IGNORECASE),
    re.compile(r"\breceived\s+(?:a\s+)?data\s+center\s+permit\b", re.IGNORECASE),
    re.compile(r"\bbought\s+land\s+for\s+(?:a\s+)?data\s+center\b", re.IGNORECASE),
    re.compile(r"\bwon\s+zoning\s+approval\b", re.IGNORECASE),
    re.compile(r"\bconnected\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?facility\s+to\s+the\s+grid\b", re.IGNORECASE),
    re.compile(r"\bcompleted\s+(?:a\s+)?data\s+center\s+expansion\b", re.IGNORECASE),
    re.compile(r"\badded\s+megawatt\s+capacity\b", re.IGNORECASE),
    re.compile(r"\bsigned\s+(?:a\s+)?data\s+center\s+lease\b", re.IGNORECASE),
    re.compile(
        r"\b(?:compute|cloud|inference|accelerator)\s+capacity\s+"
        r"(?:doubled|tripled|rose|increased|expanded|grew|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:data\s+center|datacenter)\s+capacity\s+"
        r"(?:doubled|tripled|rose|increased|expanded|grew|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:gpu|ai|training)\s+clusters?\s+"
        r"(?:doubled|tripled|rose|increased|expanded|grew|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bserver\s+fleet\s+(?:doubled|tripled|rose|increased|expanded|grew|fell|declined|dropped)\b", re.IGNORECASE),
    re.compile(r"\bcloud\s+region\s+(?:went\s+live|launched|opened)\b", re.IGNORECASE),
    re.compile(r"\bavailability\s+zone\s+(?:went\s+live|launched|opened)\b", re.IGNORECASE),
    re.compile(r"\breserved\s+compute\s+capacity\b", re.IGNORECASE),
    re.compile(r"\bramped\s+(?:up\s+)?production\b", re.IGNORECASE),
    re.compile(r"\bmoved\s+jobs\s+overseas\b", re.IGNORECASE),
    re.compile(
        r"\b(?:received|got|secured|won|gained)\s+(?:a\s+|an\s+)?"
        r"(?:regulatory|government|antitrust|court|legal|license|export)\s+"
        r"(?:approval|clearance|license)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bcleared\s+(?:a\s+)?legal\s+hurdle\b", re.IGNORECASE),
    re.compile(r"\b(?:won|settled|resolved)\s+(?:a\s+)?(?:lawsuit|case|legal\s+dispute)\b", re.IGNORECASE),
    re.compile(r"\breached\s+(?:a\s+)?settlement\b", re.IGNORECASE),
    re.compile(r"\b(?:reached|signed)\s+(?:a\s+)?product\s+liability\s+settlement\b", re.IGNORECASE),
    re.compile(r"\bcreated\s+(?:a\s+)?settlement\s+fund\b", re.IGNORECASE),
    re.compile(r"\bavoided\s+(?:a\s+)?(?:regulatory|legal|court|government)\s+ban\b", re.IGNORECASE),
    re.compile(
        r"\bfaces?\s+(?:a\s+|an\s+)?"
        r"(?:lawsuit|class\s+action|legal\s+action|antitrust\s+probe|regulatory\s+probe|probe|investigation)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:is|are|was|were)\s+(?:being\s+)?sued\b", re.IGNORECASE),
    re.compile(r"\bhit\s+with\s+(?:a\s+|an\s+)?(?:lawsuit|class\s+action|legal\s+action|probe|investigation)\b", re.IGNORECASE),
    re.compile(r"\bunder\s+(?:regulatory\s+|antitrust\s+|criminal\s+)?investigation\b", re.IGNORECASE),
    re.compile(r"\bcame\s+under\s+(?:regulatory|antitrust|legal)\s+scrutiny\b", re.IGNORECASE),
    re.compile(r"\b(?:won|lost)\s+(?:a\s+)?patent\s+(?:case|dispute)\b", re.IGNORECASE),
    re.compile(r"\bpatent\s+(?:was|were)\s+(?:invalidated|granted)\b", re.IGNORECASE),
    re.compile(r"\bfiled\s+(?:a\s+)?patent\s+infringement\s+lawsuit\b", re.IGNORECASE),
    re.compile(r"\bfaced\s+patent\s+infringement\s+claims\b", re.IGNORECASE),
    re.compile(r"\bsettled\s+(?:a\s+)?trademark\s+dispute\b", re.IGNORECASE),
    re.compile(r"\breceived\s+(?:a\s+)?copyright\s+takedown\b", re.IGNORECASE),
    re.compile(r"\bissued\s+(?:a\s+)?dmca\s+notice\b", re.IGNORECASE),
    re.compile(r"\bsigned\s+(?:a\s+)?royalty\s+agreement\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were)\s+accused\s+of\s+ip\s+theft\b", re.IGNORECASE),
    re.compile(r"\btrade\s+secret\s+case\s+(?:was|were)\s+dismissed\b", re.IGNORECASE),
    re.compile(
        r"\b(?:regulators?|authorities|ftc|doj|sec)\s+"
        r"(?:opened|launched)\s+(?:a\s+|an\s+)?(?:probe|investigation)\s+into\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:regulators?|authorities|ftc|doj|sec)\s+(?:sued|investigated)\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are|was|were)\s+fined\s+by\s+(?:regulators?|authorities|agencies|the\s+government)\b", re.IGNORECASE),
    re.compile(r"\bpaid\s+(?:a\s+|an\s+)?(?:fine|penalty)\b", re.IGNORECASE),
    re.compile(r"\bagreed\s+to\s+pay\s+(?:a\s+|an\s+)?(?:fine|penalty)\b", re.IGNORECASE),
    re.compile(r"\breceived\s+(?:a\s+|an\s+)?subpoena\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are|was|were|got)\s+sanctioned\b", re.IGNORECASE),
    re.compile(r"\bfaced\s+(?:export\s+)?restrictions\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were)\s+hit\s+by\s+(?:new\s+)?tariffs\b", re.IGNORECASE),
    re.compile(r"\btariffs\s+raised\s+chip\s+costs\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were)\s+added\s+to\s+(?:an\s+|the\s+)?export\s+blacklist\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were)\s+placed\s+on\s+(?:the\s+)?entity\s+list\b", re.IGNORECASE),
    re.compile(r"\bexport\s+license\s+(?:was|were)\s+(?:denied|revoked)\b", re.IGNORECASE),
    re.compile(r"\bfaced\s+(?:new\s+)?trade\s+curbs\b", re.IGNORECASE),
    re.compile(r"\bfaced\s+chip\s+sales\s+restrictions\b", re.IGNORECASE),
    re.compile(r"\bchip\s+sales\s+(?:were|was)\s+blocked\s+by\s+regulators?\b", re.IGNORECASE),
    re.compile(r"\bexports?\s+(?:were|was)\s+blocked\b", re.IGNORECASE),
    re.compile(r"\bshipments?\s+(?:were|was)\s+banned\s+under\s+(?:new\s+)?export\s+controls\b", re.IGNORECASE),
    re.compile(r"\blost\s+access\s+to\s+(?:china|us|u\.s\.|eu|europe)\s+sales\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are|was|were)\s+(?:barred|banned)\s+from\s+selling\b", re.IGNORECASE),
    re.compile(r"\b(?:regulators?|authorities|ftc|doj|sec|eu)\s+imposed\s+(?:a\s+|an\s+)?(?:fine|penalty)\s+on\b", re.IGNORECASE),
    re.compile(r"\b(?:sec|ftc|doj|eu)\s+(?:charged|fined|sanctioned)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:executive|ceo|cfo|coo|founder|employee|director)\s+"
        r"(?:was|were|is|are)\s+(?:arrested|indicted)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:was|were|is|are)\s+charged\s+with\s+"
        r"(?:fraud|bribery|corruption|money\s+laundering|insider\s+trading)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\badmitted\s+(?:to\s+)?bribery\b", re.IGNORECASE),
    re.compile(r"\bpaid\s+(?:a\s+)?bribes?\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were|is|are)\s+accused\s+of\s+money\s+laundering\b", re.IGNORECASE),
    re.compile(
        r"\b(?:employee|executive|ceo|cfo|coo|founder|director)\s+"
        r"(?:pleaded|pled)\s+guilty\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:was|were|is|are)\s+convicted\s+of\s+"
        r"(?:corruption|fraud|bribery|money\s+laundering|insider\s+trading)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\binsider\s+trading\s+scheme\s+surfaced\b", re.IGNORECASE),
    re.compile(r"\bembezzled\s+funds\b", re.IGNORECASE),
    re.compile(r"\bfalsified\s+records\b", re.IGNORECASE),
    re.compile(r"\bobstructed\s+justice\b", re.IGNORECASE),
    re.compile(
        r"\b(?:a\s+|the\s+)?(?:court|judge)\s+(?:approved|cleared|dismissed)\s+"
        r"(?:[a-z0-9&.'-]+\s+){0,8}(?:settlement|lawsuit|case|license|deal|acquisition)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:[a-z0-9&.'-]+\s+){0,8}"
        r"(?:license|approval|clearance|lawsuit|case|settlement)\s+"
        r"was\s+(?:approved|cleared|dismissed|settled|resolved)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bfiled\s+for\s+bankruptcy\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are|was|were)\s+preparing\s+for\s+bankruptcy\b", re.IGNORECASE),
    re.compile(r"\bdefaulted\s+on\s+debt\b", re.IGNORECASE),
    re.compile(r"\bmissed\s+(?:a\s+)?bond\s+payment\b", re.IGNORECASE),
    re.compile(r"\bissued\s+bonds\b", re.IGNORECASE),
    re.compile(r"\bsold\s+debt\b", re.IGNORECASE),
    re.compile(r"\bsecured\s+(?:a\s+)?term\s+loan\b", re.IGNORECASE),
    re.compile(r"\brefinanced\s+debt\b", re.IGNORECASE),
    re.compile(r"\bextended\s+(?:its\s+|the\s+)?credit\s+facility\b", re.IGNORECASE),
    re.compile(r"\bbreached\s+debt\s+covenants\b", re.IGNORECASE),
    re.compile(r"\breceived\s+(?:a\s+)?covenant\s+waiver\b", re.IGNORECASE),
    re.compile(r"\bwarned\s+of\s+(?:a\s+)?going\s+concern\s+risk\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are|was|were|got)\s+delisted\b", re.IGNORECASE),
    re.compile(r"\bshares?\s+(?:were|was|are|is)\s+halted\b", re.IGNORECASE),
    re.compile(r"\btrading\s+(?:was|were|is|are)\s+suspended\b", re.IGNORECASE),
    re.compile(r"\brestated\s+(?:earnings|financials?|results?|accounts?)\b", re.IGNORECASE),
    re.compile(r"\bdisclosed\s+accounting\s+errors?\b", re.IGNORECASE),
    re.compile(r"\bauditor\s+(?:resigned|quit|departed)\b", re.IGNORECASE),
    re.compile(r"\brecalled\s+(?:a\s+|an\s+|the\s+)?(?:product|device|vehicle|batch|unit|units)\b", re.IGNORECASE),
    re.compile(r"\bissued\s+(?:a\s+|an\s+)?(?:product\s+|safety\s+)?recall\b", re.IGNORECASE),
    re.compile(r"\b(?:announced|expanded)\s+(?:a\s+|an\s+)?(?:voluntary\s+|product\s+)?recall\b", re.IGNORECASE),
    re.compile(r"\bpulled\s+(?:products?|devices?|vehicles?|items?)\s+from\s+shelves\b", re.IGNORECASE),
    re.compile(r"\bwarned\s+of\s+(?:a\s+)?(?:fire|burn|choking|injury|crash|battery)\s+risk\b", re.IGNORECASE),
    re.compile(r"\bconfirmed\s+(?:a\s+)?safety\s+defect\b", re.IGNORECASE),
    re.compile(r"\breported\s+(?:injury|fire|burn|crash)\s+claims\b", re.IGNORECASE),
    re.compile(r"\bfaces?\s+product\s+safety\s+complaints\b", re.IGNORECASE),
    re.compile(r"\bhalted\s+shipments\s+over\s+safety\s+concerns\b", re.IGNORECASE),
    re.compile(r"\breceived\s+(?:an?\s+)?fda\s+warning\s+letter\b", re.IGNORECASE),
    re.compile(r"\bcured\s+(?:cancer|disease|patients?)\b", re.IGNORECASE),
    re.compile(r"\breduced\s+mortality\b", re.IGNORECASE),
    re.compile(r"\bimproved\s+patient\s+survival\b", re.IGNORECASE),
    re.compile(r"\b(?:passed|failed)\s+(?:a\s+|an\s+)?clinical\s+trial\b", re.IGNORECASE),
    re.compile(r"\breported\s+positive\s+(?:clinical\s+)?trial\s+results\b", re.IGNORECASE),
    re.compile(r"\breceived\s+(?:an?\s+)?fda\s+approval\s+for\s+(?:a\s+|an\s+)?(?:drug|therapy|treatment|device)\b", re.IGNORECASE),
    re.compile(r"\bgot\s+emergency\s+use\s+authorization\b", re.IGNORECASE),
    re.compile(r"\blaunched\s+(?:a\s+|an\s+)?new\s+therapy\b", re.IGNORECASE),
    re.compile(r"\bdiagnosed\s+patients\b", re.IGNORECASE),
    re.compile(r"\bprevented\s+(?:heart\s+attacks|strokes|infections|deaths)\b", re.IGNORECASE),
    re.compile(r"\bvaccine\s+showed\s+efficacy\b", re.IGNORECASE),
    re.compile(r"\bpublished\s+(?:a\s+|an\s+)?peer[-\s]reviewed\s+study\b", re.IGNORECASE),
    re.compile(r"\b(?:study|research|paper)\s+proved\b", re.IGNORECASE),
    re.compile(r"\bresearchers?\s+confirmed\s+(?:a\s+|an\s+)?breakthrough\b", re.IGNORECASE),
    re.compile(r"\bresearch\s+debunked\s+rivals?\b", re.IGNORECASE),
    re.compile(r"\bdiscovered\s+(?:a\s+|an\s+)?new\s+(?:material|compound|method|process)\b", re.IGNORECASE),
    re.compile(r"\binvented\s+(?:a\s+|an\s+)?new\s+(?:algorithm|material|method|process)\b", re.IGNORECASE),
    re.compile(r"\bachieved\s+quantum\s+supremacy\b", re.IGNORECASE),
    re.compile(r"\bwon\s+(?:a\s+|an\s+)?nobel\s+prize\b", re.IGNORECASE),
    re.compile(r"\breceived\s+peer\s+review\s+acceptance\b", re.IGNORECASE),
    re.compile(r"\b(?:paper|study)\s+was\s+published\s+in\s+(?:nature|science)\b", re.IGNORECASE),
    re.compile(r"\breplicated\s+the\s+findings\b", re.IGNORECASE),
    re.compile(r"\bretracted\s+(?:a\s+|an\s+)?study\b", re.IGNORECASE),
    re.compile(r"\bcaused\s+(?:an?\s+)?(?:oil\s+)?spill\b", re.IGNORECASE),
    re.compile(r"\breported\s+(?:a\s+|an\s+)?chemical\s+leak\b", re.IGNORECASE),
    re.compile(r"\breleased\s+toxic\s+(?:gas|chemicals?|waste)\b", re.IGNORECASE),
    re.compile(r"\bviolated\s+emissions\s+rules\b", re.IGNORECASE),
    re.compile(r"\bexceeded\s+pollution\s+limits\b", re.IGNORECASE),
    re.compile(r"\b(?:plant|factory|facility)\s+exploded\b", re.IGNORECASE),
    re.compile(r"\bfactory\s+fire\s+injured\s+workers\b", re.IGNORECASE),
    re.compile(r"\bdumped\s+wastewater\b", re.IGNORECASE),
    re.compile(r"\bcontaminated\s+local\s+water\b", re.IGNORECASE),
    re.compile(r"\breceived\s+(?:an?\s+)?environmental\s+violation\s+notice\b", re.IGNORECASE),
    re.compile(r"\bhalted\s+operations\s+after\s+(?:an?\s+)?environmental\s+incident\b", re.IGNORECASE),
    re.compile(r"\b(?:became|becomes|is|was)\s+(?:carbon[-\s]neutral|net[-\s]zero)\b", re.IGNORECASE),
    re.compile(r"\b(?:reached|achieved|hit|met)\s+(?:carbon[-\s]neutral|net[-\s]zero)\b", re.IGNORECASE),
    re.compile(r"\bcut\s+carbon\s+emissions\b", re.IGNORECASE),
    re.compile(
        r"\breduced\s+(?:carbon\s+emissions|water\s+usage|water\s+use|energy\s+use|energy\s+consumption)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:energy\s+consumption|electricity\s+use|power\s+consumption)\s+"
        r"(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<!renewable\s)\benergy\s+use\s+"
        r"(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:carbon\s+emissions|co2\s+emissions|greenhouse\s+gas\s+emissions|ghg\s+emissions)\s+"
        r"(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<!carbon\s)(?<!co2\s)(?<!gas\s)(?<!ghg\s)(?<!scope\s1\s)(?<!scope\s2\s)(?<!scope\s3\s)"
        r"\bemissions\s+(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bscope\s+[123]\s+emissions\s+"
        r"(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:water\s+usage|water\s+use|water\s+consumption|water\s+withdrawals?)\s+"
        r"(?:surged|spiked|rose|increased|doubled|tripled|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\brenewable\s+energy\s+(?:use|usage|share)\s+"
        r"(?:improved|worsened|rose|increased|doubled|tripled|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:power\s+usage\s+effectiveness|pue)\s+"
        r"(?:improved|worsened|rose|increased|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:waste\s+reduction|recycling\s+rate|carbon\s+footprint|emissions\s+intensity)\s+"
        r"(?:improved|rose|increased|doubled|tripled|fell|declined|dropped)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bpowered\s+(?:facilities|data\s+centers?|operations)\s+with\s+renewable\s+energy\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bsigned\s+(?:a\s+)?renewable\s+energy\s+deal\b", re.IGNORECASE),
    re.compile(r"\bfaced\s+greenwashing\s+(?:allegations|claims|complaints)\b", re.IGNORECASE),
    re.compile(r"\b(?:was|were)\s+accused\s+of\s+greenwashing\b", re.IGNORECASE),
    re.compile(r"\bfailed\s+(?:an?\s+)?esg\s+audit\b", re.IGNORECASE),
    re.compile(r"\breceived\s+(?:a\s+)?sustainability\s+certification\b", re.IGNORECASE),
    re.compile(r"\bmissed\s+climate\s+targets?\b", re.IGNORECASE),
    re.compile(r"\breported\s+scope\s+[123]\s+emissions\s+(?:increased|rose|fell|dropped)\b", re.IGNORECASE),
    re.compile(r"\blike\s+never\s+before\b", re.IGNORECASE),
    re.compile(r"\b(?<!like\s)never\s+before\b", re.IGNORECASE),
    re.compile(r"\b(?:largest|biggest|highest|lowest|fastest)\b", re.IGNORECASE),
    re.compile(r"\bfirst[-\s]ever\b", re.IGNORECASE),
    re.compile(r"\b(?:became|becomes|is|was)\s+the\s+first\b", re.IGNORECASE),
    re.compile(r"\bfirst\s+[a-z][a-z0-9&.\- ]{0,60}?\s+to\b", re.IGNORECASE),
    re.compile(
        "(?<![\\w\\uac00-\\ud7a3])(?:\\uc5ed\\ub300|\\uc0ac\\uc0c1)\\s*"
        "(?:\\ucd5c\\uace0\\uce58?|\\ucd5c\\uc800\\uce58?)"
        "(?:\\uc744|\\ub97c|\\uc774|\\uac00|\\uc758|\\ub85c)?",
        re.IGNORECASE,
    ),
    re.compile(
        "(?<![\\w\\uac00-\\ud7a3])(?:\\ucd5c\\ub300|\\ucd5c\\ucd08)(?:\\ub85c|\\uc758)?",
        re.IGNORECASE,
    ),
)


def _has_prohibited_analogy(text: str) -> bool:
    return any(pattern.search(text) for pattern in _PROHIBITED_ANALOGY_PATTERNS)


def _count_emojis(text: str) -> int:
    count = 0
    for ch in text:
        code = ord(ch)
        if any(start <= code <= end for start, end in _EMOJI_RANGES):
            count += 1
    return count


def _count_clipped_endings(text: str) -> int:
    count = 0
    for chunk in re.split(r"[.!?\n]+", text):
        sentence = chunk.strip()
        if sentence.endswith(("임", "음")):
            count += 1
    return count


def _trend_is_ai_native(trend: ScoredTrend) -> bool:
    parts = [
        getattr(trend, "keyword", ""),
        getattr(trend, "category", ""),
        getattr(trend, "top_insight", ""),
        getattr(trend, "why_trending", ""),
        getattr(trend, "best_hook_starter", ""),
    ]
    parts.extend(getattr(trend, "suggested_angles", []) or [])
    context = getattr(trend, "context", None)
    if context:
        parts.append(context.to_combined_text())
    text = "\n".join(part for part in parts if part).lower()
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _AI_NATIVE_PATTERNS)


def _score_hook(lead_text: str, leading_lines: list[str], group_name: str) -> tuple[int, list[str]]:
    """훅 점수 (16점 만점): 첫 문장 품질 평가."""
    issues: list[str] = []
    score = 16
    if any(phrase in lead_text for phrase in _QA_CLICHE_PATTERNS):
        score = max(0, score - 6)
        issues.append("첫 문장이 기사체/상투구에 가까움")
    if not re.search(r"\d|왜|무엇|핵심|신호|질문", lead_text):
        score = max(0, score - 3)
    if group_name == "long_posts" and len(leading_lines) < 2:
        score = max(0, score - 4)
        issues.append("첫 3줄 안의 핵심 주장 구조가 약함")
    return score, issues


def _cliche_tone_penalty(matched_cliches: list[str]) -> tuple[int, str] | None:
    if not matched_cliches:
        return None
    return min(15, 5 * len(matched_cliches)), f"상투구 감지: {', '.join(matched_cliches[:3])}"


def _analogy_tone_penalty(combined: str) -> tuple[int, str] | None:
    if not _has_prohibited_analogy(combined):
        return None
    return 8, "비유/은유 표현 감지"


def _korean_nlp_tone_penalties(
    combined: str,
    items: list[GeneratedTweet],
    matched_cliches: list[str],
) -> list[tuple[int, str]]:
    try:
        from korean_nlp import compute_quality_score, detect_ai_voice
    except ImportError:
        return []

    penalties: list[tuple[int, str]] = []
    ai_flags = detect_ai_voice(combined)
    if ai_flags:
        new_flags = [f for f in ai_flags if not any(c in f for c in matched_cliches)]
        if new_flags:
            penalties.append((min(10, 3 * len(new_flags)), f"AI어투(형태소): {', '.join(new_flags[:2])}"))
    avg_quality = sum(compute_quality_score(item.content) for item in items if item.content) / max(len(items), 1)
    if avg_quality < 0.5:
        penalties.append((3, f"Kiwipiepy 품질 점수 낮음: {avg_quality:.2f}"))
    return penalties


def _slang_tone_penalty(combined: str) -> tuple[int, str] | None:
    matched_slang = [pattern for pattern in _BANNED_SLANG_PATTERNS if pattern in combined]
    if not matched_slang:
        return None
    return min(8, 4 * len(matched_slang)), f"persona slang detected: {', '.join(matched_slang[:2])}"


def _emoji_tone_penalty(combined: str) -> tuple[int, str] | None:
    emoji_count = _count_emojis(combined)
    if emoji_count <= 1:
        return None
    return min(6, (emoji_count - 1) * 2), f"emoji overuse: {emoji_count}"


def _clipped_ending_tone_penalty(combined: str) -> tuple[int, str] | None:
    clipped_endings = _count_clipped_endings(combined)
    if clipped_endings <= 2:
        return None
    return min(6, clipped_endings - 2), f"repeated clipped endings: {clipped_endings}"


def _ai_framing_mentions(combined: str) -> int:
    return len(
        re.findall(
            r"\bai\b|\bgpt\b|\bllm\b|\bagent(?:s)?\b|\bclaude\b|\bopenai\b|\bgemini\b",
            combined.lower(),
        )
    )


def _ai_framing_tone_penalty(combined: str, trend: ScoredTrend | None) -> tuple[int, str] | None:
    if trend is None:
        return None
    ai_mentions = _ai_framing_mentions(combined)
    if _trend_is_ai_native(trend) or ai_mentions <= 2:
        return None
    return min(8, ai_mentions - 2), f"AI framing overuse: {ai_mentions}"


def _tone_penalties(
    combined: str,
    items: list[GeneratedTweet],
    matched_cliches: list[str],
    trend: ScoredTrend | None,
) -> list[tuple[int, str]]:
    penalties = [
        _cliche_tone_penalty(matched_cliches),
        _analogy_tone_penalty(combined),
        *_korean_nlp_tone_penalties(combined, items, matched_cliches),
        _slang_tone_penalty(combined),
        _emoji_tone_penalty(combined),
        _clipped_ending_tone_penalty(combined),
        _ai_framing_tone_penalty(combined, trend),
    ]
    return [penalty for penalty in penalties if penalty is not None]


def _score_tone(
    combined: str, items: list[GeneratedTweet], matched_cliches: list[str], trend: ScoredTrend | None = None
) -> tuple[int, list[str]]:
    """어투 점수 (15점 만점): 상투구, AI어투, 슬랭, 이모지, clipped ending 탐지."""
    issues: list[str] = []
    score = 15
    for penalty, issue in _tone_penalties(combined, items, matched_cliches, trend):
        score = max(0, score - penalty)
        issues.append(issue)

    return score, issues


def _score_fact(combined: str, trend: ScoredTrend) -> tuple[int, bool, list[str]]:
    """Score factual grounding against the trend context."""
    issues: list[str] = []
    score = 15
    fact_violation = False

    allowed_corpus = _build_allowed_fact_corpus(trend)
    entity_penalty, entity_issue = _unknown_entity_fact_penalty(combined, allowed_corpus)
    if entity_penalty:
        score = max(0, score - entity_penalty)
        fact_violation = True
        issues.append(entity_issue)

    percentage_penalty, percentage_issue = _unknown_percentage_fact_penalty(combined, allowed_corpus)
    if percentage_penalty:
        score = max(0, score - percentage_penalty)
        fact_violation = True
        issues.append(percentage_issue)

    number_penalty, number_issue = _unknown_number_fact_penalty(combined, allowed_corpus)
    if number_penalty:
        score = max(0, score - number_penalty)
        fact_violation = True
        issues.append(number_issue)

    date_penalty, date_issue = _unknown_date_fact_penalty(combined, allowed_corpus)
    if date_penalty:
        score = max(0, score - date_penalty)
        fact_violation = True
        issues.append(date_issue)

    strong_claim_penalty, strong_claim_issue = _unknown_strong_claim_fact_penalty(combined, allowed_corpus)
    if strong_claim_penalty:
        score = max(0, score - strong_claim_penalty)
        fact_violation = True
        issues.append(strong_claim_issue)

    if not allowed_corpus.lower().strip():
        score = min(score, 10)

    domain_penalty, domain_issue = _unknown_domain_attribution_fact_penalty(combined, allowed_corpus)
    if domain_penalty:
        score = max(0, score - domain_penalty)
        fact_violation = True
        issues.append(domain_issue)

    outlet_penalty, outlet_issue = _unknown_outlet_attribution_fact_penalty(combined, allowed_corpus)
    if outlet_penalty:
        score = max(0, score - outlet_penalty)
        fact_violation = True
        issues.append(outlet_issue)

    quote_penalty, quote_issue = _unverified_quote_fact_penalty(combined)
    if quote_penalty:
        score = max(0, score - quote_penalty)
        fact_violation = True
        issues.append(quote_issue)

    consistency_issues = _number_consistency_issues(combined)
    if consistency_issues:
        score = max(0, score - 3 * len(consistency_issues))
        issues.extend(consistency_issues)

    return score, fact_violation, issues


def _normalized_candidate_entities(text: str) -> set[str]:
    entity_allowlist = _GENERIC_ENTITY_ALLOWLIST | _ATTRIBUTION_MARKER_ALLOWLIST
    return {e.casefold() for e in _extract_candidate_entities(text) if e.casefold() not in entity_allowlist}


def _unknown_entity_fact_penalty(combined: str, allowed_corpus: str) -> tuple[int, str]:
    unknown_entities = sorted(_normalized_candidate_entities(combined) - _normalized_candidate_entities(allowed_corpus))
    if not unknown_entities:
        return 0, ""
    display_entities = unknown_entities[:2]
    return min(10, 4 * len(display_entities)), f"컨텍스트 밖 고유명사 추정: {', '.join(display_entities)}"


def _unknown_percentage_fact_penalty(combined: str, allowed_corpus: str) -> tuple[int, str]:
    allowed_percentages = _normalized_percentage_claims(allowed_corpus)
    unknown_percentages = sorted(_normalized_percentage_claims(combined) - allowed_percentages)
    if not unknown_percentages:
        return 0, ""
    display_percentages = unknown_percentages[:2]
    return min(8, 3 * len(display_percentages)), f"컨텍스트 밖 수치 추정: {', '.join(display_percentages)}"


def _normalized_percentage_claims(text: str) -> set[str]:
    return {
        re.sub(r"\s+", "", claim.strip().casefold())
        .replace("퍼센트", "%")
        .replace("프로", "%")
        for claim in _PERCENTAGE_CLAIM_RE.findall(text)
    }


def _normalized_number_claims(text: str) -> set[str]:
    concrete_claims = _CONCRETE_NUMBER_CLAIM_RE.findall(text)
    currency_text = _CONCRETE_NUMBER_CLAIM_RE.sub(" ", text)
    currency_claims = _CURRENCY_NUMBER_CLAIM_RE.findall(currency_text)
    bare_text = _CURRENCY_NUMBER_CLAIM_RE.sub(" ", currency_text)
    bare_claims = _SIGNIFICANT_BARE_NUMBER_CLAIM_RE.findall(bare_text)
    korean_claims = _KOREAN_NUMBER_CLAIM_RE.findall(text)
    return {
        re.sub(r"[\s,]+", "", claim.strip().casefold())
        for claim in [*concrete_claims, *currency_claims, *bare_claims, *korean_claims]
    }


def _unknown_number_fact_penalty(combined: str, allowed_corpus: str) -> tuple[int, str]:
    allowed_numbers = _normalized_number_claims(allowed_corpus)
    unknown_numbers = sorted(_normalized_number_claims(combined) - allowed_numbers)
    if not unknown_numbers:
        return 0, ""
    display_numbers = unknown_numbers[:2]
    return min(8, 3 * len(display_numbers)), f"unsupported numeric claim: {', '.join(display_numbers)}"


def _normalized_date_claims(text: str) -> set[str]:
    claims = [
        *list(_EXPLICIT_DATE_CLAIM_RE.findall(text)),
        *list(_KOREAN_DATE_CLAIM_RE.findall(text)),
    ]
    return {
        re.sub(r"[\s,]+", "", claim.strip().casefold())
        for claim in claims
    }


def _unknown_date_fact_penalty(combined: str, allowed_corpus: str) -> tuple[int, str]:
    allowed_dates = _normalized_date_claims(allowed_corpus)
    unknown_dates = sorted(_normalized_date_claims(combined) - allowed_dates)
    if not unknown_dates:
        return 0, ""
    display_dates = unknown_dates[:2]
    return min(8, 4 * len(display_dates)), f"unsupported date claim: {', '.join(display_dates)}"


def _normalized_strong_claims(text: str) -> set[str]:
    return {
        _normalize_strong_claim_phrase(match.group(0))
        for pattern in _STRONG_CLAIM_REGEXES
        for match in pattern.finditer(text)
    }


def _normalize_strong_claim_phrase(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().casefold().replace("-", " "))
    return re.sub("(\\uc744|\\ub97c|\\uc774|\\uac00|\\uc758|\\ub85c)$", "", normalized)


def _unknown_strong_claim_fact_penalty(combined: str, allowed_corpus: str) -> tuple[int, str]:
    allowed_claims = _normalized_strong_claims(allowed_corpus)
    unknown_claims = sorted(_normalized_strong_claims(combined) - allowed_claims)
    if not unknown_claims:
        return 0, ""
    display_claims = unknown_claims[:2]
    return min(8, 4 * len(display_claims)), f"unsupported strong claim: {', '.join(display_claims)}"


def _normalized_domains(text: str) -> set[str]:
    return {domain.casefold().removeprefix("www.") for domain in _DOMAIN_CANDIDATE_RE.findall(text)}


def _normalized_domain_attributions(text: str) -> set[str]:
    return {
        domain.casefold().removeprefix("www.")
        for pattern in _DOMAIN_ATTRIBUTION_REGEXES
        for domain in pattern.findall(text)
    }


def _unknown_domain_attribution_fact_penalty(combined: str, allowed_corpus: str) -> tuple[int, str]:
    allowed_domains = _normalized_domains(allowed_corpus)
    unknown_domains = sorted(_normalized_domain_attributions(combined) - allowed_domains)
    if not unknown_domains:
        return 0, ""
    display_domains = unknown_domains[:2]
    return min(8, 4 * len(display_domains)), f"unsupported source domain attribution: {', '.join(display_domains)}"


def _normalize_outlet_name(name: str) -> str:
    normalized = re.sub(r"\s+", " ", name.strip().casefold())
    return normalized.removeprefix("the ")


def _normalized_outlets(text: str) -> set[str]:
    return {_normalize_outlet_name(match.group(1)) for match in _OUTLET_NAME_PATTERN.finditer(text)}


def _normalized_outlet_attributions(text: str) -> set[str]:
    return {
        _normalize_outlet_name(match.group(1))
        for pattern in _OUTLET_ATTRIBUTION_REGEXES
        for match in pattern.finditer(text)
    }


def _unknown_outlet_attribution_fact_penalty(combined: str, allowed_corpus: str) -> tuple[int, str]:
    allowed_outlets = _normalized_outlets(allowed_corpus)
    unknown_outlets = sorted(_normalized_outlet_attributions(combined) - allowed_outlets)
    if not unknown_outlets:
        return 0, ""
    display_outlets = unknown_outlets[:2]
    return min(8, 4 * len(display_outlets)), f"unsupported source outlet attribution: {', '.join(display_outlets)}"


def _unverified_quote_fact_penalty(combined: str) -> tuple[int, str]:
    matched_unverified = [p for p in _UNVERIFIED_QUOTE_PATTERNS if p in combined]
    matched_attribution = [
        match.group(0)
        for pattern in _UNVERIFIED_ATTRIBUTION_REGEXES
        for match in pattern.finditer(combined)
    ]
    if not matched_unverified and not matched_attribution:
        return 0, ""
    display_matches = [*matched_unverified, *matched_attribution][:2]
    penalty_count = len(matched_unverified) + len(matched_attribution)
    return min(10, 5 * penalty_count), f"출처 불명 인용 감지: {', '.join(display_matches)}"


def _number_consistency_issues(combined: str) -> list[str]:
    content_numbers = re.findall(r"(\d{1,3}(?:[,.]?\d{3})*(?:\.\d+)?)\s*(만|억|조|%)", combined)
    if len(content_numbers) < 2:
        return []
    return [
        f"수치 불일치 의심: 같은 단위({unit})에서 차이 큼"
        for unit, vals in _numbers_by_unit(content_numbers).items()
        if len(vals) >= 2 and max(vals) / max(min(vals), 0.01) > 100
    ]


def _numbers_by_unit(content_numbers: list[tuple[str, str]]) -> dict[str, list[float]]:
    by_unit: dict[str, list[float]] = {}
    for num_str, unit in content_numbers:
        with contextlib.suppress(ValueError):
            by_unit.setdefault(unit, []).append(float(num_str.replace(",", "")))
    return by_unit


def _score_kick(combined: str) -> tuple[int, list[str]]:
    """마무리 점수 (12점 만점): 상투적 결말 탐지."""
    issues: list[str] = []
    ending = combined.splitlines()[-1] if combined.splitlines() else combined
    if any(phrase in ending for phrase in ("귀추가 주목된다", "마무리하며", "결론적으로")):
        issues.append("마무리가 상투적임")
        return 4, issues
    return 12, issues


def _apply_tweet_format_rules(
    items: list[GeneratedTweet], angle: int, regulation: int, algorithm: int
) -> tuple[int, int, int, list[str]]:
    issues: list[str] = []
    if any(len(item.content) > 240 for item in items):
        regulation = min(regulation, 6)
        algorithm = min(algorithm, 6)
        issues.append("240자 초과 트윗 존재")
    if any(len(item.content) < 160 for item in items):
        angle = max(0, angle - 4)
        algorithm = max(0, algorithm - 2)
        issues.append("160자 미만 트윗 존재 (정보 밀도 부족)")
    angle, algorithm, missing_type_issues = _apply_missing_tweet_type_format_rules(items, angle, algorithm)
    angle, algorithm, repeated_type_issues = _apply_repeated_tweet_type_format_rules(items, angle, algorithm)
    issues.extend(missing_type_issues + repeated_type_issues)
    return angle, regulation, algorithm, issues


def _normalized_tweet_type(tweet_type: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", tweet_type.strip().casefold())


_KOREAN_PARTICLE_PATTERN = (
    r"으로|에서|에게|부터|까지|하고|은|는|이|가|을|를|과|와|도|만|의|로|에|께|랑"
)
_KOREAN_PARTICLE_BOUNDARY_RE = re.compile(
    rf"(?<=[가-힣A-Za-z0-9])(?:{_KOREAN_PARTICLE_PATTERN})(?=\s|[^\w]|$)"
)
_KOREAN_PARTICLE_SPACING_RE = re.compile(
    rf"(?<=[가-힣A-Za-z0-9])\s+(?=(?:{_KOREAN_PARTICLE_PATTERN})(?=\s|[^\w]|$))"
)


def _apply_missing_tweet_type_format_rules(
    items: list[GeneratedTweet], angle: int, algorithm: int
) -> tuple[int, int, list[str]]:
    missing_count = sum(1 for item in items if not _normalized_tweet_type(item.tweet_type))
    if missing_count <= 0:
        return angle, algorithm, []
    angle = max(0, angle - min(4, 2 * missing_count))
    algorithm = max(0, algorithm - min(4, 2 * missing_count))
    return angle, algorithm, [f"missing tweet_type variant: {missing_count} item(s)"]


def _apply_repeated_tweet_type_format_rules(
    items: list[GeneratedTweet], angle: int, algorithm: int
) -> tuple[int, int, list[str]]:
    tweet_types = [_normalized_tweet_type(item.tweet_type) for item in items]
    tweet_types = [tweet_type for tweet_type in tweet_types if tweet_type]
    repeated_count = len(tweet_types) - len(set(tweet_types))
    if repeated_count <= 0:
        return angle, algorithm, []
    angle = max(0, angle - min(4, 2 * repeated_count))
    algorithm = max(0, algorithm - min(4, 2 * repeated_count))
    return angle, algorithm, [f"repeated tweet_type variant: {repeated_count} repeated item(s)"]


_DRAFT_SOCIAL_DECORATION_RE = re.compile(r"https?://\S+|www\.\S+|(?<!\w)#\w+|@\w+", re.IGNORECASE)
_DRAFT_LEADING_MARKER_RE = re.compile(r"(?m)^\s*(?:\d+\s*[\).:/-]\s*|[-*+]\s+)")
_DRAFT_CORE_SIGNATURE_MIN_LENGTH = 80
_DRAFT_HOOK_SIGNATURE_MIN_LENGTH = 24
_DRAFT_KICK_SIGNATURE_MIN_LENGTH = 24


def _compact_draft_signature(content: str) -> str:
    normalized = content.strip().casefold()
    normalized = _KOREAN_PARTICLE_SPACING_RE.sub("", normalized)
    normalized = _KOREAN_PARTICLE_BOUNDARY_RE.sub("", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _normalized_draft_signature(content: str) -> str:
    return _compact_draft_signature(content)


def _is_draft_decoration_char(char: str) -> bool:
    if char.isalnum() or char.isspace():
        return False
    return unicodedata.category(char)[0] in {"P", "S"}


def _strip_draft_decorations(content: str) -> str:
    stripped = _DRAFT_SOCIAL_DECORATION_RE.sub(" ", content)
    stripped = _DRAFT_LEADING_MARKER_RE.sub(" ", stripped)
    return "".join(" " if _is_draft_decoration_char(char) else char for char in stripped)


def _normalized_draft_core_signature(content: str) -> str:
    normalized = _compact_draft_signature(_strip_draft_decorations(content))
    if len(normalized) < _DRAFT_CORE_SIGNATURE_MIN_LENGTH:
        return ""
    return normalized


def _opening_hook_text(content: str) -> str:
    stripped = _strip_draft_decorations(content)
    chunks = [chunk.strip() for chunk in re.split(r"[\n.!?]+", stripped) if chunk.strip()]
    return chunks[0] if chunks else ""


def _normalized_opening_hook_signature(content: str) -> str:
    normalized = _compact_draft_signature(_opening_hook_text(content))
    if len(normalized) < _DRAFT_HOOK_SIGNATURE_MIN_LENGTH:
        return ""
    return normalized


def _closing_kick_text(content: str) -> str:
    stripped = _DRAFT_SOCIAL_DECORATION_RE.sub(" ", content)
    stripped = _DRAFT_LEADING_MARKER_RE.sub(" ", stripped)
    chunks = [chunk.strip() for chunk in re.split(r"[\n.!?]+", stripped) if chunk.strip()]
    return _strip_draft_decorations(chunks[-1]) if chunks else ""


def _normalized_closing_kick_signature(content: str) -> str:
    normalized = _compact_draft_signature(_closing_kick_text(content))
    if len(normalized) < _DRAFT_KICK_SIGNATURE_MIN_LENGTH:
        return ""
    return normalized


def _duplicate_signature_indices(signatures: list[tuple[int, str]]) -> set[int]:
    seen: dict[str, int] = {}
    duplicates: set[int] = set()
    for idx, signature in signatures:
        if not signature:
            continue
        if signature in seen:
            duplicates.add(idx)
        else:
            seen[signature] = idx
    return duplicates


def _apply_duplicate_draft_format_rules(
    items: list[GeneratedTweet], angle: int, algorithm: int
) -> tuple[int, int, list[str]]:
    exact_signatures: list[tuple[int, str]] = []
    core_signatures: list[tuple[int, str]] = []
    for idx, item in enumerate(items):
        if not item.content.strip():
            continue
        exact_signatures.append((idx, _normalized_draft_signature(item.content)))
        core_signature = _normalized_draft_core_signature(item.content)
        if core_signature:
            core_signatures.append((idx, core_signature))

    duplicate_indices = _duplicate_signature_indices(exact_signatures)
    duplicate_indices.update(_duplicate_signature_indices(core_signatures))
    duplicate_count = len(duplicate_indices)
    if duplicate_count <= 0:
        return angle, algorithm, []
    angle = max(0, angle - min(6, 3 * duplicate_count))
    algorithm = max(0, algorithm - min(4, 2 * duplicate_count))
    return angle, algorithm, [f"duplicate generated draft: {duplicate_count} repeated item(s)"]


def _apply_repeated_opening_hook_format_rules(
    items: list[GeneratedTweet], angle: int, algorithm: int
) -> tuple[int, int, list[str]]:
    signatures = [
        (idx, _normalized_opening_hook_signature(item.content))
        for idx, item in enumerate(items)
        if item.content.strip()
    ]
    duplicate_count = len(_duplicate_signature_indices(signatures))
    if duplicate_count <= 0:
        return angle, algorithm, []
    angle = max(0, angle - min(4, 2 * duplicate_count))
    algorithm = max(0, algorithm - min(4, 2 * duplicate_count))
    return angle, algorithm, [f"repeated opening hook: {duplicate_count} repeated item(s)"]


def _apply_repeated_closing_kick_format_rules(
    items: list[GeneratedTweet], angle: int, algorithm: int
) -> tuple[int, int, list[str]]:
    signatures = [
        (idx, _normalized_closing_kick_signature(item.content))
        for idx, item in enumerate(items)
        if item.content.strip()
    ]
    duplicate_count = len(_duplicate_signature_indices(signatures))
    if duplicate_count <= 0:
        return angle, algorithm, []
    angle = max(0, angle - min(4, 2 * duplicate_count))
    algorithm = max(0, algorithm - min(4, 2 * duplicate_count))
    return angle, algorithm, [f"repeated closing kick: {duplicate_count} repeated item(s)"]


def _apply_threads_format_rules(
    items: list[GeneratedTweet], combined: str, angle: int, regulation: int, algorithm: int
) -> tuple[int, int, int, list[str]]:
    issues: list[str] = []
    if "#" in combined:
        regulation = 0
        issues.append("해시태그 사용")
    matched_bait = [p for p in _THREADS_BAIT_PATTERNS if p in combined]
    if matched_bait:
        regulation = max(0, regulation - 6)
        issues.append(f"李몄뿬 ?좊룄 臾멸뎄 媛먯?: {', '.join(matched_bait[:2])}")
    if any(len(item.content) > 500 for item in items):
        algorithm = max(0, algorithm - 4)
        issues.append("500자 초과 Threads 포스트 존재")
    return angle, regulation, algorithm, issues


def _apply_long_post_format_rules(combined: str, angle: int, regulation: int, algorithm: int) -> tuple[int, int, int, list[str]]:
    if not re.search(r"\n", combined):
        angle = max(0, angle - 4)
    return angle, regulation, algorithm, []


def _apply_blog_format_rules(combined: str, angle: int, regulation: int, algorithm: int) -> tuple[int, int, int, list[str]]:
    issues: list[str] = []
    missing = [h for h in _BLOG_REQUIRED_HEADINGS if h not in combined]
    if missing:
        angle = max(0, angle - min(12, 3 * len(missing)))
        issues.append(f"필수 섹션 누락: {', '.join(missing)}")
    if "## 핵심 정리" in combined and not re.search(r"(?m)^[\-\*\u2022]\s+", combined):
        angle = max(0, angle - 4)
        issues.append("핵심 정리 불릿 부족")
    return angle, regulation, algorithm, issues


def _score_format(
    group_name: str,
    items: list[GeneratedTweet],
    combined: str,
) -> tuple[int, int, int, list[str]]:
    """Score platform-specific content format rules."""
    angle, regulation, algorithm = 12, 10, 10
    handlers = {
        "tweets": lambda: _apply_tweet_format_rules(items, angle, regulation, algorithm),
        "threads_posts": lambda: _apply_threads_format_rules(items, combined, angle, regulation, algorithm),
        "long_posts": lambda: _apply_long_post_format_rules(combined, angle, regulation, algorithm),
        "blog_posts": lambda: _apply_blog_format_rules(combined, angle, regulation, algorithm),
    }
    handler = handlers.get(group_name)
    if handler is None:
        issues: list[str] = []
    else:
        angle, regulation, algorithm, issues = handler()
    angle, algorithm, duplicate_issues = _apply_duplicate_draft_format_rules(items, angle, algorithm)
    angle, algorithm, hook_issues = _apply_repeated_opening_hook_format_rules(items, angle, algorithm)
    angle, algorithm, kick_issues = _apply_repeated_closing_kick_format_rules(items, angle, algorithm)
    return angle, regulation, algorithm, issues + duplicate_issues + hook_issues + kick_issues

def _audit_content_group(
    group_name: str,
    items: list[GeneratedTweet],
    trend: ScoredTrend,
    config: AppConfig,
) -> dict:
    combined = "\n".join(item.content for item in items if item.content)
    leading_lines = _first_nonempty_lines(combined, limit=3)
    lead_text = " ".join(leading_lines)
    matched_cliches = [p for p in _QA_CLICHE_PATTERNS if p in combined]

    hook, hook_issues = _score_hook(lead_text, leading_lines, group_name)
    tone, tone_issues = _score_tone(combined, items, matched_cliches, trend)
    fact, fact_violation, fact_issues = _score_fact(combined, trend)
    kick, kick_issues = _score_kick(combined)
    angle, regulation, algorithm, fmt_issues = _score_format(group_name, items, combined)

    issues = hook_issues + tone_issues + fact_issues + kick_issues + fmt_issues

    total = hook + fact + tone + kick + angle + regulation + algorithm
    threshold = config.get_quality_threshold(group_name)
    failed = total < threshold or regulation <= 3 or fact_violation
    reason = issues[0] if issues else "통과"
    scores = {
        "hook": hook,
        "fact": fact,
        "tone": tone,
        "kick": kick,
        "angle": angle,
        "regulation": regulation,
        "algorithm": algorithm,
    }
    worst = min(scores.items(), key=lambda item: item[1])[0]
    return {
        **scores,
        "total": total,
        "avg_score": total,
        "threshold": threshold,
        "fact_violation": fact_violation,
        "failed": failed,
        "worst": worst,
        "reason": reason,
        "issues": issues,
    }


def _content_group_map(batch: "TweetBatch") -> dict[str, list[GeneratedTweet]]:
    return {
        "tweets": list(getattr(batch, "tweets", []) or []),
        "threads_posts": list(getattr(batch, "threads_posts", []) or []),
        "long_posts": list(getattr(batch, "long_posts", []) or []),
        "blog_posts": list(getattr(batch, "blog_posts", []) or []),
    }


def _audit_present_groups(
    present_groups: dict[str, list[GeneratedTweet]],
    trend: "ScoredTrend",
    config: "AppConfig",
) -> tuple[dict[str, dict], list[str]]:
    group_results: dict[str, dict] = {}
    failed_groups: list[str] = []
    for group_name, items in present_groups.items():
        result = _audit_content_group(group_name, items, trend, config)
        group_results[group_name] = result
        if result["failed"]:
            failed_groups.append(group_name)
        log.info(
            f"  [QA:{group_name}] '{trend.keyword}' 점수 {result['total']}/{result['threshold']} "
            f"(F:{result['fact']} T:{result['tone']} R:{result['regulation']})"
        )
    _apply_cross_platform_duplicate_results(present_groups, group_results, failed_groups)
    return group_results, failed_groups


def _cross_platform_draft_signatures(content: str) -> list[str]:
    if not content.strip():
        return []
    exact_signature = _normalized_draft_signature(content)
    core_signature = _normalized_draft_core_signature(content)
    signatures = [signature for signature in (exact_signature, core_signature) if len(signature) >= _DRAFT_CORE_SIGNATURE_MIN_LENGTH]
    return list(dict.fromkeys(signatures))


def _cross_platform_duplicate_issues(present_groups: dict[str, list[GeneratedTweet]]) -> dict[str, list[str]]:
    first_seen: dict[str, tuple[str, int]] = {}
    duplicate_issues: dict[str, list[str]] = {}
    duplicate_items: set[tuple[str, int]] = set()
    for group_name, items in present_groups.items():
        for idx, item in enumerate(items):
            signatures = _cross_platform_draft_signatures(item.content)
            duplicate_of: tuple[str, int] | None = None
            for signature in signatures:
                existing = first_seen.get(signature)
                if existing and existing[0] != group_name:
                    duplicate_of = existing
                    break
            for signature in signatures:
                first_seen.setdefault(signature, (group_name, idx))
            if duplicate_of is None or (group_name, idx) in duplicate_items:
                continue
            duplicate_items.add((group_name, idx))
            source_group, source_idx = duplicate_of
            duplicate_issues.setdefault(group_name, []).append(
                "cross-platform duplicate generated draft: "
                f"{group_name} item {idx + 1} repeats {source_group} item {source_idx + 1}"
            )
    return duplicate_issues


def _apply_cross_platform_duplicate_results(
    present_groups: dict[str, list[GeneratedTweet]],
    group_results: dict[str, dict],
    failed_groups: list[str],
) -> None:
    duplicate_issues = _cross_platform_duplicate_issues(present_groups)
    for group_name, issues in duplicate_issues.items():
        result = group_results.get(group_name)
        if not result:
            continue
        duplicate_count = len(issues)
        result["angle"] = max(0, result["angle"] - min(6, 3 * duplicate_count))
        result["algorithm"] = max(0, result["algorithm"] - min(4, 2 * duplicate_count))
        result["total"] = result["hook"] + result["fact"] + result["tone"] + result["kick"] + result["angle"] + result["regulation"] + result["algorithm"]
        result["avg_score"] = result["total"]
        result["issues"].extend(issues)
        result["failed"] = True
        result["reason"] = issues[0]
        result["worst"] = min(
            (
                ("hook", result["hook"]),
                ("fact", result["fact"]),
                ("tone", result["tone"]),
                ("kick", result["kick"]),
                ("angle", result["angle"]),
                ("regulation", result["regulation"]),
                ("algorithm", result["algorithm"]),
            ),
            key=lambda item: item[1],
        )[0]
        if group_name not in failed_groups:
            failed_groups.append(group_name)


def _audit_summary(group_results: dict[str, dict], failed_groups: list[str]) -> dict:
    summary_total = round(sum(r["total"] for r in group_results.values()) / len(group_results))
    summary_regulation = min(r["regulation"] for r in group_results.values())
    primary_result = group_results.get("tweets") or next(iter(group_results.values()))
    summary_reason = (
        " | ".join(f"{group}: {result['reason']}" for group, result in group_results.items() if result["failed"])
        or "통과"
    )
    summary_worst = min(group_results.items(), key=lambda item: item[1]["total"])[0]

    return {
        **primary_result,
        "total": summary_total,
        "avg_score": summary_total,
        "regulation": summary_regulation,
        "reason": summary_reason,
        "worst": summary_worst,
        "failed_groups": failed_groups,
        "group_results": group_results,
    }


async def audit_generated_content(
    batch: "TweetBatch",
    trend: "ScoredTrend",
    config: "AppConfig",
    client: "LLMClient",
) -> dict | None:
    """Audit generated content and return group-level retry details."""
    if not batch:
        return None

    present_groups = {name: items for name, items in _content_group_map(batch).items() if items}
    if not present_groups:
        return None

    group_results, failed_groups = _audit_present_groups(present_groups, trend, config)
    return _audit_summary(group_results, failed_groups)

def build_regeneration_feedback(
    *,
    qa_summary: dict | None = None,
    fact_check_results: dict | None = None,
) -> dict[str, dict]:
    """Normalize QA / fact-check failures into per-group retry feedback."""
    feedback: dict[str, dict] = {}
    _add_qa_regeneration_feedback(feedback, qa_summary or {})
    _add_fact_check_regeneration_feedback(feedback, fact_check_results or {})

    return feedback


def _add_qa_regeneration_feedback(feedback: dict[str, dict], qa_summary: dict) -> None:
    qa_failed_groups = set(qa_summary.get("failed_groups", []) or [])
    for group_name, result in qa_summary.get("group_results", {}).items():
        if result.get("failed") or group_name in qa_failed_groups:
            feedback.setdefault(group_name, {})["qa"] = _qa_regeneration_feedback(result)

    for group_name in qa_failed_groups:
        feedback.setdefault(group_name, {}).setdefault("qa", _default_qa_regeneration_feedback())


def _qa_regeneration_feedback(result: dict) -> dict:
    return {
        "total": result.get("total"),
        "threshold": result.get("threshold"),
        "reason": result.get("reason", ""),
        "issues": list(result.get("issues", []) or [])[:3],
        "worst_axis": result.get("worst", ""),
        "regulation": result.get("regulation"),
        "fact_violation": bool(result.get("fact_violation")),
    }


def _default_qa_regeneration_feedback() -> dict:
    return {
        "total": "?",
        "threshold": "?",
        "reason": "",
        "issues": [],
        "worst_axis": "",
        "regulation": 10,
        "fact_violation": False,
    }


def _add_fact_check_regeneration_feedback(feedback: dict[str, dict], fact_check_results: dict) -> None:
    for group_name, fc_result in fact_check_results.items():
        if _fact_check_requires_regeneration(fc_result):
            feedback.setdefault(group_name, {})["fact_check"] = _fact_check_regeneration_feedback(fc_result)


def _fact_check_requires_regeneration(fc_result: object) -> bool:
    hallucinated_claims = int(getattr(fc_result, "hallucinated_claims", 0) or 0)
    return not getattr(fc_result, "passed", True) or hallucinated_claims > 0


def _fact_check_regeneration_feedback(fc_result: object) -> dict:
    return {
        "summary": getattr(fc_result, "summary", ""),
        "issues": list(getattr(fc_result, "issues", []) or [])[:3],
        "accuracy_score": getattr(fc_result, "accuracy_score", None),
        "hallucinated_claims": int(getattr(fc_result, "hallucinated_claims", 0) or 0),
        "unverified_claims": int(getattr(fc_result, "unverified_claims", 0) or 0),
    }


def _load_regeneration_generators() -> dict[str, object]:
    # Import lazily to avoid circular imports while generator.py re-exports
    # these helpers from content_qa.py for backward compatibility.
    try:
        from .generator import (
            _select_generation_tier,
            generate_blog_async,
            generate_long_form_async,
            generate_threads_content_async,
            generate_tweets_async,
        )
    except ImportError:
        from generator import (
            _select_generation_tier,
            generate_blog_async,
            generate_long_form_async,
            generate_threads_content_async,
            generate_tweets_async,
        )

    return {
        "select_generation_tier": _select_generation_tier,
        "generate_blog": generate_blog_async,
        "generate_long_form": generate_long_form_async,
        "generate_threads": generate_threads_content_async,
        "generate_tweets": generate_tweets_async,
    }


def _merge_group_feedback(
    group_name: str,
    qa_feedback: dict[str, dict] | None,
    fact_check_feedback: dict[str, dict] | None,
) -> dict | None:
    merged: dict = {}
    if qa_feedback and group_name in qa_feedback:
        merged.update(qa_feedback[group_name])
    if fact_check_feedback and group_name in fact_check_feedback:
        merged.update(fact_check_feedback[group_name])
    return merged or None


def _long_form_regeneration_enabled(groups: list[str], config: "AppConfig", trend: "ScoredTrend") -> bool:
    return "long_posts" in groups and config.enable_long_form and trend.viral_potential >= config.long_form_min_score


def _blog_regeneration_enabled(groups: list[str], config: "AppConfig", trend: "ScoredTrend") -> bool:
    return (
        "blog_posts" in groups
        and "naver_blog" in getattr(config, "target_platforms", [])
        and trend.viral_potential >= getattr(config, "blog_min_score", 70)
    )


def _feedback_for(
    group_name: str,
    qa_feedback: dict[str, dict] | None,
    fact_check_feedback: dict[str, dict] | None,
) -> dict | None:
    return _merge_group_feedback(group_name, qa_feedback, fact_check_feedback)


def _build_regeneration_tasks(
    trend: "ScoredTrend",
    config: "AppConfig",
    client: "LLMClient",
    groups: list[str],
    recent_tweets: list[str] | None,
    approved_post_bank: list[dict] | None,
    qa_feedback: dict[str, dict] | None,
    fact_check_feedback: dict[str, dict] | None,
) -> dict[str, asyncio.Task]:
    generators = _load_regeneration_generators()
    regen_tasks: dict[str, asyncio.Task] = {}
    if "tweets" in groups:
        regen_tasks["tweets"] = asyncio.create_task(
            generators["generate_tweets"](
                trend,
                config,
                client,
                recent_tweets,
                approved_post_bank,
                revision_feedback=_feedback_for("tweets", qa_feedback, fact_check_feedback),
            )
        )
    if "threads_posts" in groups:
        regen_tasks["threads_posts"] = asyncio.create_task(
            generators["generate_threads"](
                trend,
                config,
                client,
                revision_feedback=_feedback_for("threads_posts", qa_feedback, fact_check_feedback),
            )
        )
    if _long_form_regeneration_enabled(groups, config, trend):
        regen_tasks["long_posts"] = asyncio.create_task(
            generators["generate_long_form"](
                trend,
                config,
                client,
                tier=generators["select_generation_tier"](trend, config),
                revision_feedback=_feedback_for("long_posts", qa_feedback, fact_check_feedback),
            )
        )
    if _blog_regeneration_enabled(groups, config, trend):
        regen_tasks["blog_posts"] = asyncio.create_task(
            generators["generate_blog"](
                trend,
                config,
                client,
                revision_feedback=_feedback_for("blog_posts", qa_feedback, fact_check_feedback),
            )
        )
    return regen_tasks


def _apply_regenerated_group(batch: "TweetBatch", trend: "ScoredTrend", group_name: str, result: object) -> None:
    if isinstance(result, Exception):
        log.warning(f"  [QA 재생성 실패] '{trend.keyword}' {group_name}: {result}")
        return
    if group_name == "tweets":
        if result and getattr(result, "tweets", None):
            batch.tweets = result.tweets
        return
    if result is not None:
        setattr(batch, group_name, result)


async def regenerate_content_groups(
    batch: "TweetBatch",
    trend: "ScoredTrend",
    config: "AppConfig",
    client: "LLMClient",
    groups: list[str],
    recent_tweets: list[str] | None = None,
    approved_post_bank: list[dict] | None = None,
    *,
    qa_feedback: dict[str, dict] | None = None,
    fact_check_feedback: dict[str, dict] | None = None,
) -> "TweetBatch":
    """Regenerate failed content groups once and merge them back into a batch."""
    if not groups:
        return batch

    regen_tasks = _build_regeneration_tasks(
        trend,
        config,
        client,
        groups,
        recent_tweets,
        approved_post_bank,
        qa_feedback,
        fact_check_feedback,
    )
    if not regen_tasks:
        return batch

    results = await asyncio.gather(*regen_tasks.values(), return_exceptions=True)
    for group_name, result in zip(regen_tasks.keys(), results, strict=False):
        _apply_regenerated_group(batch, trend, group_name, result)
    return batch

#  v15.0 Phase B: Named Persona Rotation
#  → generation/persona.py로 추출됨
# ══════════════════════════════════════════════════════

try:
    from .generation.persona import _CATEGORY_PERSONA_MAP, _round_robin_counter, select_persona  # noqa: F401
except ImportError:
    from generation.persona import _CATEGORY_PERSONA_MAP, _round_robin_counter, select_persona  # noqa: F401
