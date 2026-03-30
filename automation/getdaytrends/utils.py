"""
getdaytrends - 공통 유틸리티
이벤트 루프 관리 등 여러 모듈에서 공유하는 헬퍼 함수.
"""

import asyncio
import concurrent.futures
import re

# ══════════════════════════════════════════════════════
#  Prompt Injection Guard
# ══════════════════════════════════════════════════════

_INJECTION_PATTERNS = re.compile(
    r"ignore\s+(?:all\s+)?(?:previous|above|prior)"
    r"|disregard\s+(?:all\s+)?(?:previous|above)"
    r"|forget\s+(?:all\s+)?(?:previous|above)"
    r"|(?:^|\s)system\s*:"
    r"|(?:^|\s)assistant\s*:"
    r"|(?:^|\s)user\s*:"
    r"|<\s*(?:system|assistant|user|prompt|instructions)\s*>"
    r"|\[(?:SYSTEM|INST|\/INST)\]",
    flags=re.IGNORECASE,
)


def sanitize_keyword(keyword: str, max_len: int = 200) -> str:
    """
    LLM 프롬프트에 삽입되는 키워드 정제.
    프롬프트 인젝션 패턴 차단 + 길이 제한 + 제어문자 제거.
    """
    if not keyword:
        return ""
    keyword = keyword[:max_len]
    # 제어문자 제거 (탭·줄바꿈 제외)
    keyword = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", keyword)
    keyword = _INJECTION_PATTERNS.sub("***", keyword)
    return keyword.strip()


# ══════════════════════════════════════════════════════
#  Async Helpers
# ══════════════════════════════════════════════════════

_PY314_SHUTDOWN_TIMEOUT_MSG = "Timeout should be used inside a task"


def _run_coroutine_in_new_loop(coro):
    """
    새 이벤트 루프에서 코루틴 실행.

    Python 3.14 환경에서 일부 라이브러리가 `nest_asyncio` 스타일로 루프를
    패치한 경우 `shutdown_default_executor()` 정리 단계에서
    `RuntimeError: Timeout should be used inside a task`가 발생할 수 있다.
    실제 코루틴 실행이 끝난 뒤 이 종료 단계에서만 터지는 문제이므로,
    해당 케이스는 무시하고 루프를 닫는다.
    """
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(coro)
        loop.run_until_complete(loop.shutdown_asyncgens())

        shutdown_default_executor = getattr(loop, "shutdown_default_executor", None)
        if shutdown_default_executor is not None:
            try:
                loop.run_until_complete(shutdown_default_executor())
            except RuntimeError as exc:
                if _PY314_SHUTDOWN_TIMEOUT_MSG not in str(exc):
                    raise

        return result
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def run_async(coro):
    """
    코루틴을 동기 컨텍스트에서 실행.

    이벤트 루프가 이미 실행 중이면(Jupyter 등) 스레드풀을 통해 실행하고,
    아니면 전용 이벤트 루프에서 실행한다.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_run_coroutine_in_new_loop, coro).result()

    return _run_coroutine_in_new_loop(coro)
