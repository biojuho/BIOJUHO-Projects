"""
generation/audit.py — Content Quality Audit & Regeneration
==========================================================

✅ 마이그레이션 완료: QA 코드는 `content_qa.py`로 이동되었습니다.

이 모듈은 하위 호환성을 위해 유지되며, content_qa.py를 참조합니다.

포함된 함수:
- _build_allowed_fact_corpus
- _extract_candidate_entities
- _first_nonempty_lines
- _audit_content_group
- audit_generated_content
- regenerate_content_groups

사용법:
    from generation.audit import audit_generated_content, regenerate_content_groups
    # 또는 직접:
    from content_qa import audit_generated_content, regenerate_content_groups
"""

# Re-export from content_qa for backward compatibility
from content_qa import (
    audit_generated_content,
    regenerate_content_groups,
)

__all__ = [
    "audit_generated_content",
    "regenerate_content_groups",
]
