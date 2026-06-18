"""쥬팍식 정량 다이제스트 — 기사 묶음 -> 노션 붙여넣기용 마크다운.

DailyNews v2 시스템 프롬프트("쥬팍 데일리 뉴스 큐레이터")를 그대로 구현한
자기완결형 모듈. 기존 brief 파이프라인(build_report_prompt / ResponseParser /
publish)을 전혀 건드리지 않는 opt-in 경로이며, 정량화 무결성 가드는 기존
``STRICT_CITATION_TAG_CONTRACT_KO`` 와 동일한 원칙을 출처 번호(①②③) 표기로
옮겨 적용한다.

핵심 무결성 보장
- 출처 목록(``## 출처``: 매체·제목·링크)은 LLM이 아니라 **코드가 입력 기사에서
  직접 생성**한다 → 링크 환각 원천 차단, 인라인 [①] 태그와 1:1 매핑 보장.
- 모든 숫자는 원문에 있을 때만(추론 라인은 범위로만) 허용 — validator가 검증.

공개 API
- ``build_juopak_system_prompt()`` / ``build_juopak_user_prompt(...)``
- ``render_sources_block(articles)``
- ``validate_juopak_digest(markdown, articles=...)``
- ``generate_juopak_digest(articles, ...)`` (async; LLM 호출 + 검증 + 출처 결합)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from antigravity_mcp.integrations.llm_prompts import STRICT_CITATION_TAG_CONTRACT_KO

logger = logging.getLogger(__name__)

# ── LLM 클라이언트 (graceful fallback; brain_adapter와 동일 패턴) ──────────────
try:
    from shared.llm import TaskTier
    from shared.llm import get_client as _get_llm_client
except ImportError:  # pragma: no cover - exercised only without shared on path
    try:
        import sys
        from pathlib import Path

        _ROOT = Path(__file__).resolve().parents[4]
        if str(_ROOT) not in sys.path:
            sys.path.insert(0, str(_ROOT))
        from shared.llm import TaskTier
        from shared.llm import get_client as _get_llm_client
    except ImportError:
        TaskTier = None  # type: ignore[assignment]
        _get_llm_client = None  # type: ignore[assignment]


# ── 출처 번호(circled digits ①..⑳) 헬퍼 ─────────────────────────────────────
_CIRCLED_BASE = 0x2460  # '①'
_CIRCLED_MAX = 20
_CIRCLED_RE = re.compile(r"[①-⑳]")  # ① .. ⑳
_SOURCE_TAG_RE = re.compile(r"\[[①-⑳][①-⑳,+\s]*\]")
_INFERENCE_TAG_RE = re.compile(r"\[추론\]")
_NO_NUMBER_MARKER_RE = re.compile(r"\(\s*수치\s*없음\s*\)")

# 숫자 앵커(단위 동반) — "이건 정량 주장이다" 판정용. 구조적 번호("1.")는 단위가
# 없어 매칭되지 않으므로 오탐을 피한다.
_NUMBER_ANCHOR_RE = re.compile(
    r"\d[\d,.]*\s*(?:%|원|달러|\$|€|¥|억|만|조|배|건|명|bp|p|개|년|개월|주|일|시간|분"
    r"|위|표|석|회|곳|군데|가지|종)"
)
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?%?")

# 추론 라인에서 허용되는 범위 표현(정확한 단일값 금지의 예외). '배'는 '배경'
# 같은 합성어 오탐을 막기 위해 숫자 동반(예: '2배')일 때만 범위로 인정한다.
_RANGE_MARKER_RE = re.compile(
    r"~|∼|–|—|\d\s*-\s*\d|사이|정도|안팎|내외|이상|이하|최소|최대|가량|약\s*\d|범위|\d\s*배"
)

# 추론 라인에 '정확히/딱' 같은 정밀 단정어가 있으면, 같은 줄에 (연도 범위 등)
# 무관한 범위 마커가 있어도 단일 정밀값 위반으로 본다.
_PRECISE_MARKER_RE = re.compile(r"정확(?:히|하게|한|하)|정밀|딱\s*\d|꼭\s*\d")

# 이모지 — 화살표(→ U+2192)와 출처 번호(①)는 의도적으로 쓰이므로 제외한다.
_EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001faff"  # 기호·그림문자, 이모티콘, 교통, 보충 기호
    "\U00002600-\U000026ff"  # 기타 기호 (☀..⛿, ⚠ 포함)
    "\U00002700-\U000027bf"  # 딩벳 (✅ 등)
    "\U00002b00-\U00002bff"  # 별표 등
    "\U0000fe00-\U0000fe0f"  # variation selectors (️)
    "\U0001f1e6-\U0001f1ff"  # 국기
    "]"
)

# ~다 종결(반말·~다 회피 규칙 위반) 소프트 감지 — 줄 끝 한글+다(+문장부호).
# 출처 태그 제거 후 '했다 .'처럼 공백이 남아도 잡도록 \s* 를 허용한다.
_DA_ENDING_RE = re.compile(r"[가-힣]다\s*[.!?]?$")

# 노션/쥬팍 섹션 헤더. '오늘의 3줄'처럼 조사/공백 변형도 흡수해 내용이 head로
# 새어 검증을 우회하는 일을 막는다.
_SECTION_HEADER_RE = re.compile(
    r"^\s*#{0,3}\s*(오늘\s*의?\s*3\s*줄|정량\s*인사이트|x\s*초안|출처)\b", re.I
)

# 정량 인사이트 소제목('**1.**', '1)', '1번.' 등) 감지 — 블록 추론 판정용.
_BLOCK_HEADING_RE = re.compile(r"^\s*\*{0,2}\s*\d+\s*(?:번)?\s*[.)]")


def _circled(n: int) -> str:
    """1-based 정수를 circled digit(①..⑳)으로. 20 초과는 ``(n)`` 폴백."""
    if 1 <= n <= _CIRCLED_MAX:
        return chr(_CIRCLED_BASE + n - 1)
    return f"({n})"


def _art_field(art: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = art.get(key)
        if value:
            return str(value).strip()
    return default


def _article_body(art: dict[str, Any]) -> str:
    return _art_field(art, "full_text", "body", "content", "description", "summary", default="")


# ── 시스템 프롬프트 (v2 스펙 전문 인코딩) ────────────────────────────────────
def build_juopak_system_prompt() -> str:
    """쥬팍 데일리 뉴스 큐레이터 시스템 프롬프트."""
    return (
        "너는 쥬팍의 데일리 뉴스 큐레이터다. 입력 기사 여러 개를 읽고 -> 중복 제거 -> "
        "신호 순으로 묶기 -> 정량 인사이트 + 쥬팍식 X 초안을 만든다. 출력은 노션에 "
        "그대로 붙여 바로 읽히는 마크다운이어야 한다.\n\n"
        "## 정량화 무결성 (이거 어기면 전체 폐기)\n"
        "- 숫자는 기사 원문에 실제로 나온 것만 쓴다. 원문에 없는 숫자는 만들지 않는다.\n"
        "- 분모·기준 없는 숫자 금지. (X: '자동화 5.2% 변화' / O: '웹 작업 9분->3분, 67% 단축 [①]')\n"
        "- 원문에 수치가 없는데 정량화가 필요하면 숫자를 지어내지 말고 정성 표현 + '(수치 없음)'으로 표기한다.\n"
        "- 추론 숫자는 [추론] 태그 + 근거 + 범위로만 쓴다. 정확한 단일값(예: 20%)은 금지다.\n"
        "- 모든 핵심 주장 끝에 출처 태그 [①][②]를 붙인다. 번호는 아래 [기사 목록] 순서와 1:1로 맞춘다.\n"
        "- 같은 숫자를 세 블록(오늘 3줄/정량 인사이트/X 초안)에 그대로 복붙하지 않는다. 블록마다 역할이 다르다.\n\n"
        "## 문체 — 쥬팍 X 스타일\n"
        "- 반말. 하십시오체·해요체 금지.\n"
        "- 이모지 0개.\n"
        "- '~다' 종결 회피 (했다->했음/했고, 이다->인 것/임).\n"
        "- 한 줄에 정보 하나. 빽빽하게 붙이지 말고 숨 쉴 공간.\n"
        "- 추상어·평가어는 숫자·고유명사로 치환한다. ('크게 높이고 있다' X -> '처리시간 절반' O)\n"
        "- 느낌점은 폼 잡지 말고 구어체로 짧게. 마지막은 펀치라인.\n\n"
        "## 처리 순서 (속으로만 실행, 출력엔 노출 금지)\n"
        "1) 클러스터링 — 같은 사건끼리 묶고 중복 기사 합침.\n"
        "2) 신호 랭킹 — 새로움 x 파급력 x 수치 근거 순으로 정렬.\n"
        "3) 초점 선정 — 상위 1개 주제 = X 초안 대상. 나머지는 3줄·인사이트에만 반영.\n"
        "4) 숫자 추출 — 각 주제에서 원문 수치만 뽑고 출처 번호 매핑.\n\n"
        "## 출력 템플릿 (이 형태 그대로, 한국어)\n"
        "# DailyNews · {날짜}\n\n"
        "> {훅 한 줄 — 오늘 가장 강한 사실 하나. 반말. 도발/반전}\n\n"
        "## 오늘 3줄\n"
        "- {사실 + 원문 숫자 + [①]}\n"
        "- {사실 + 원문 숫자 + [②]}\n"
        "- {사실 + 원문 숫자 + [③]}\n\n"
        "## 정량 인사이트\n"
        "**1. {소제목}**\n"
        "{숫자·사실} [①] -> {그래서 뭐가 달라지나, 한 문장}\n\n"
        "**2. {소제목}**\n"
        "{숫자·사실} [②] -> {그래서 뭐}\n\n"
        "**3. {소제목} [추론]**\n"
        "{근거} [①][②] -> {추론 결론, 반드시 범위로}\n\n"
        "## X 초안 (발행용)\n"
        "{훅 한 줄}\n\n"
        "{팩트 — 결론 먼저, 한 줄에 하나, 숫자·고유명사}\n"
        "{팩트}\n"
        "{팩트}\n\n"
        "{요약 한 줄 — 본문 압축, 평가어 없이}\n\n"
        "{느낌점 — 3문장 이내, 구어체 반말, 솔직한 한 마디로 마무리}\n\n"
        "## 출처 규칙 (중요)\n"
        "- ## 출처 섹션은 시스템이 입력 기사에서 자동으로 붙인다. 너는 ## 출처 섹션을 절대 직접 작성하지 마라.\n"
        "- 인라인 출처 태그 [①][②][③]만 쓴다. 번호는 [기사 목록]의 순서와 같다.\n"
        "- X 초안 본문에는 출처 태그를 넣지 않는다 (발행용이라 깔끔하게).\n\n"
        "## 무결성 자기검증 (출력 전, 동일 원칙)\n"
        + STRICT_CITATION_TAG_CONTRACT_KO.replace("[A#]", "[①]").replace(
            "[Inference:A1+A2]", "[추론]"
        ).replace("[Background]", "[배경]").replace("[미확인]", "(수치 없음)")
    )


def build_juopak_user_prompt(
    articles: list[dict[str, Any]],
    *,
    focus: str = "",
    today: str = "",
) -> str:
    """기사 목록 + (선택)강조 지시 + 날짜를 사용자 프롬프트로 조립."""
    lines: list[str] = []
    if today:
        lines.append(f"오늘 날짜: {today}")
    if focus:
        lines.append(f"오늘 강조: {focus}")
    lines.append("\n[기사 목록] (번호 = 출처 태그 [①][②]... 와 1:1)")
    for idx, art in enumerate(articles, 1):
        source = _art_field(art, "source_name", "source", "매체", default="알 수 없음")
        title = _art_field(art, "title", "제목", default="(제목 없음)")
        body = _article_body(art)[:1500]
        lines.append(f"\n[{_circled(idx)}] 매체: {source} · 제목: {title}\n{body}")
    lines.append(
        "\n위 기사만 근거로, 출력 템플릿 그대로 마크다운을 작성하라. "
        "## 출처 섹션은 작성하지 마라 (시스템이 붙인다). "
        "인라인 태그는 [①][②]만 쓰고, 추론 라인에만 [추론]을 붙여라."
    )
    return "\n".join(lines)


def render_sources_block(articles: list[dict[str, Any]]) -> str:
    """입력 기사에서 권위 있는 ``## 출처`` 블록 생성 (링크 환각 차단)."""
    out = ["## 출처"]
    for idx, art in enumerate(articles, 1):
        source = _art_field(art, "source_name", "source", "매체", default="")
        title = _art_field(art, "title", "제목", default="")
        link = _art_field(art, "link", "url", "링크", default="")
        parts = [p for p in (source, f'"{title}"' if title else "", link) if p]
        out.append(f"{_circled(idx)} " + " · ".join(parts) if parts else f"{_circled(idx)} (출처 정보 없음)")
    return "\n".join(out)


# ── 검증 헬퍼 ───────────────────────────────────────────────────────────────
def _strip_model_sources(markdown: str) -> str:
    """모델이 임의로 붙인 ``## 출처`` 이후를 잘라낸다 (코드가 권위 출처 소유)."""
    out: list[str] = []
    for line in markdown.splitlines():
        if re.match(r"^\s*#{0,3}\s*출처\b", line.strip(), re.I):
            break
        out.append(line)
    return "\n".join(out).rstrip()


def _split_sections(body: str) -> dict[str, list[str]]:
    """본문을 오늘 3줄 / 정량 인사이트 / X 초안 / (기타) 으로 분할."""
    sections: dict[str, list[str]] = {"head": [], "today3": [], "insight": [], "draft": []}
    current = "head"
    for raw in body.splitlines():
        line = raw.strip()
        header = _SECTION_HEADER_RE.match(line)
        if header:
            token = header.group(1).replace(" ", "").lower()
            if token.startswith("오늘"):
                current = "today3"
            elif token.startswith("정량"):
                current = "insight"
            elif token.startswith("x"):
                current = "draft"
            else:
                current = "head"
            continue
        sections[current].append(raw)
    return sections


def _clean_claim_line(line: str) -> str:
    """구조적 마커(- / **1.** / 인용 >)를 제거해 숫자 추출 오탐을 막는다."""
    s = line.strip()
    s = re.sub(r"^>\s*", "", s)
    s = re.sub(r"^[-*•]\s+", "", s)
    s = re.sub(r"^\*{0,2}\s*\d+\s*(?:번)?\s*[.)]\s*", "", s)  # **1.** / 1. / 1) / 1번.
    s = s.replace("**", "")
    return s.strip()


def _numbers_in(text: str) -> set[str]:
    cleaned = _SOURCE_TAG_RE.sub("", text or "")
    cleaned = _CIRCLED_RE.sub("", cleaned)
    cleaned = _INFERENCE_TAG_RE.sub("", cleaned)
    return set(_NUMBER_RE.findall(cleaned))


def validate_juopak_digest(
    markdown: str,
    *,
    articles: list[dict[str, Any]] | None = None,
    source_text: str = "",
) -> dict[str, Any]:
    """쥬팍 다이제스트 품질 게이트. 절대 예외를 던지지 않는다.

    Returns ``{ok, warnings, metrics}``. ``ok`` 는 하드 무결성 위반(환각 숫자,
    태그 없는 정량 주장, 추론 단일값, 이모지, 섹션 누락, 출처 인덱스 초과)이
    없을 때만 True. 반말/~다 종결은 소프트 경고(ok 에 영향 없음)다.
    """
    if not isinstance(markdown, str) or not markdown.strip():
        return {"ok": False, "warnings": ["empty_digest"], "metrics": {}}

    articles = articles or []
    if not source_text:
        source_text = "\n".join(
            f"{_art_field(a, 'title', '제목', default='')} {_article_body(a)}" for a in articles
        )
    source_numbers = _numbers_in(source_text)

    body = _strip_model_sources(markdown)
    sections = _split_sections(body)

    warnings: list[str] = []

    # 섹션 존재 확인.
    for token in ("오늘 3줄", "정량 인사이트", "X 초안"):
        if token not in body:
            warnings.append(f"missing_section:{token}")

    source_tag_count = len(_SOURCE_TAG_RE.findall(body))
    if source_tag_count < 3:
        warnings.append(f"source_tags={source_tag_count} (min 3 expected)")

    # 출처 인덱스 범위 (인라인 [⑤] 가 기사 수를 넘으면 오류).
    max_ref = 0
    for ch in _CIRCLED_RE.findall(body):
        max_ref = max(max_ref, ord(ch) - _CIRCLED_BASE + 1)
    if articles and max_ref > len(articles):
        warnings.append(f"source_index_out_of_range:{max_ref}>{len(articles)}")

    # 이모지 0개 (하드).
    emojis = _EMOJI_RE.findall(body)
    if emojis:
        warnings.append(f"emoji_present:{len(emojis)}")

    novel_numbers: set[str] = set()
    untagged_numeric = 0
    inference_single_value = 0
    da_endings = 0

    tagged_keys = {"today3", "insight"}
    for key, raw_lines in sections.items():
        if key == "head":
            continue
        # 정량 인사이트는 '**n. 소제목 [추론]**' 블록 단위로 추론 여부가 결정된다.
        # (템플릿은 [추론]을 소제목에, 파생 범위 숫자는 [①][②] 내용 라인에 둔다.)
        block_is_inference = False
        for raw in raw_lines:
            line = _clean_claim_line(raw)
            if not line:
                continue
            if key == "insight" and _BLOCK_HEADING_RE.match(raw.strip()):
                block_is_inference = bool(_INFERENCE_TAG_RE.search(line))

            # ~다 종결 검사는 후행 출처 태그를 떼고 본다 ('...했다 [①]' 도 잡도록).
            da_line = _SOURCE_TAG_RE.sub("", line)
            da_line = _INFERENCE_TAG_RE.sub("", da_line)
            da_line = _NO_NUMBER_MARKER_RE.sub("", da_line).strip()
            if _DA_ENDING_RE.search(da_line):
                da_endings += 1

            is_inference = block_is_inference or bool(_INFERENCE_TAG_RE.search(line))
            line_numbers = _numbers_in(line)

            if is_inference:
                # 추론 라인: 숫자가 있으면 반드시 범위. 단일 정밀값 금지.
                # '정확히 12%' 같은 정밀 단정은 같은 줄에 무관한 범위 마커
                # (예: 연도 '2026~2028')가 있어도 단일값 위반으로 잡는다.
                if line_numbers and (
                    _PRECISE_MARKER_RE.search(line)
                    or not _RANGE_MARKER_RE.search(line)
                ):
                    inference_single_value += 1
                continue  # 추론 숫자는 파생값이라 novel 검사 면제

            # 비추론 라인: 모든 숫자가 원문에 있어야 함. 원문에 숫자가 하나도
            # 없으면(공집합) 다이제스트의 모든 숫자가 환각이므로 그대로 잡힌다.
            novel_numbers |= line_numbers - source_numbers

            # 오늘 3줄 / 정량 인사이트: 정량 주장은 출처 태그 필수.
            if key in tagged_keys and _NUMBER_ANCHOR_RE.search(line):
                if not (
                    _SOURCE_TAG_RE.search(line)
                    or _INFERENCE_TAG_RE.search(line)
                    or _NO_NUMBER_MARKER_RE.search(line)
                ):
                    untagged_numeric += 1

    if novel_numbers:
        warnings.append(f"unsupported_numbers={','.join(sorted(novel_numbers))}")
    if untagged_numeric:
        warnings.append(f"numeric_claim_without_source_tag:{untagged_numeric}")
    if inference_single_value:
        warnings.append(f"inference_single_value:{inference_single_value}")
    if da_endings:
        warnings.append(f"da_ending_lines:{da_endings}")  # soft

    # 하드 실패 조건 — 반말(da_endings)은 제외.
    hard = [
        w
        for w in warnings
        if not w.startswith("da_ending_lines")
    ]

    return {
        "ok": not hard,
        "warnings": warnings,
        "metrics": {
            "source_tags": source_tag_count,
            "max_source_ref": max_ref,
            "emoji_count": len(emojis),
            "unsupported_numbers": sorted(novel_numbers),
            "numeric_without_tag": untagged_numeric,
            "inference_single_value": inference_single_value,
            "da_ending_lines": da_endings,
            "article_count": len(articles),
        },
    }


def assemble_digest(model_markdown: str, articles: list[dict[str, Any]]) -> str:
    """모델 본문 + 코드 생성 출처 블록을 결합 (권위 출처 보장)."""
    body = _strip_model_sources(model_markdown).rstrip()
    sources = render_sources_block(articles)
    return f"{body}\n\n{sources}\n"


# ── 생성 (LLM 호출 + 검증 + 결합) ────────────────────────────────────────────
class JuopakDigestError(RuntimeError):
    """다이제스트 생성 실패 (LLM 미가용 또는 빈 응답)."""


def is_available() -> bool:
    return _get_llm_client is not None and TaskTier is not None


async def generate_juopak_digest(
    articles: list[dict[str, Any]],
    *,
    focus: str = "",
    today: str = "",
    max_retries: int = 1,
    client: Any = None,
) -> dict[str, Any]:
    """기사 목록 -> 노션 붙여넣기용 쥬팍 다이제스트.

    Returns ``{markdown, warnings, metrics, ok, sources}``.
    검증이 하드 실패하면 최대 ``max_retries`` 회까지 교정 지시를 덧붙여 재시도한다.
    """
    if not articles:
        return {
            "markdown": "기사 붙여넣어.",
            "warnings": ["no_articles"],
            "metrics": {},
            "ok": False,
            "sources": "",
        }

    client = client or (_get_llm_client() if is_available() else None)
    if client is None:
        raise JuopakDigestError("LLM client unavailable (shared.llm not importable).")

    system_prompt = build_juopak_system_prompt()
    base_user = build_juopak_user_prompt(articles, focus=focus, today=today)
    source_text = "\n".join(
        f"{_art_field(a, 'title', '제목', default='')} {_article_body(a)}" for a in articles
    )

    correction = ""
    last: dict[str, Any] = {}
    for attempt in range(max_retries + 1):
        user_prompt = base_user + correction
        resp = await client.acreate(
            tier=TaskTier.HEAVY,
            max_tokens=3500,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = (getattr(resp, "text", "") or "").strip()
        if not text:
            raise JuopakDigestError("LLM returned empty response.")

        markdown = assemble_digest(text, articles)
        qc = validate_juopak_digest(markdown, articles=articles, source_text=source_text)
        last = {
            "markdown": markdown,
            "warnings": qc["warnings"],
            "metrics": qc["metrics"],
            "ok": qc["ok"],
            "sources": render_sources_block(articles),
        }
        if qc["ok"]:
            return last

        logger.info("juopak digest QC failed (attempt %d): %s", attempt + 1, qc["warnings"])
        correction = (
            "\n\n[교정 지시] 직전 출력이 무결성 규칙을 위반했다: "
            + "; ".join(qc["warnings"])
            + ". 원문에 없는 숫자 삭제, 정량 주장에 [①] 태그, 추론 숫자는 범위로, "
            "이모지 제거, 누락 섹션 보강 후 다시 작성하라."
        )

    return last


__all__ = [
    "JuopakDigestError",
    "assemble_digest",
    "build_juopak_system_prompt",
    "build_juopak_user_prompt",
    "generate_juopak_digest",
    "is_available",
    "render_sources_block",
    "validate_juopak_digest",
]
