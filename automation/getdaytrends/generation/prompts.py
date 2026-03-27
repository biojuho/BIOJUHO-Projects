"""
generation/prompts.py — System Prompt Templates & Section Builders
================================================================

✅ 마이그레이션 완료: 프롬프트 코드는 `prompt_builder.py`로 이동되었습니다.

이 모듈은 하위 호환성을 위해 유지되며, prompt_builder.py를 참조합니다.

포함 내용:
- 페르소나 규칙 (_JOONGYEON_RULES 등)
- System prompt 빌더 (_system_tweets, _system_long_form 등)
- Section 빌더 (_build_context_section, _build_scoring_section 등)
- 언어 매핑 (_LANG_NAME_MAP)
- 티어 선택 (_select_generation_tier)

사용법:
    from generation.prompts import _system_tweets, _select_generation_tier
    # 또는 직접:
    from prompt_builder import _system_tweets, _select_generation_tier
"""

# Re-export from prompt_builder for backward compatibility
from prompt_builder import (
    _LANG_NAME_MAP,
    _retry_generate,
    _select_generation_tier,
    _resolve_language,
)

# Re-export from generation.system_prompts
try:
    from generation.system_prompts import (
        _system_tweets,
        _system_long_form,
        _system_threads,
    )
except ImportError:
    # Fallback if system_prompts.py doesn't exist yet
    _system_tweets = None
    _system_long_form = None
    _system_threads = None

__all__ = [
    '_LANG_NAME_MAP',
    '_retry_generate',
    '_select_generation_tier',
    '_resolve_language',
    '_system_tweets',
    '_system_long_form',
    '_system_threads',
]
