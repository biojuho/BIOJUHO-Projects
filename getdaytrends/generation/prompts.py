"""
generation/prompts.py — System Prompt Templates & Section Builders
================================================================

Phase 2.5: generator.py에서 추출된 프롬프트 관련 함수 및 상수.
현재 generator.py에서 import하여 사용 (하위 호환 유지).

포함 내용:
- 페르소나 규칙 (_JOONGYEON_RULES 등)
- System prompt 빌더 (_system_tweets, _system_long_form 등)
- Section 빌더 (_build_context_section, _build_scoring_section 등)

TODO: generator.py L370-L755의 프롬프트 코드를 이 파일로 마이그레이션 예정.
현재는 generator.py에서 역방향 임포트 구조로 호환성 유지.
"""

# Phase 2.5: 마이그레이션 준비 완료.
# generator.py의 프롬프트 섹션은 단계적으로 이 파일로 이동됩니다.
# 각 함수 이동 시 generator.py에서는 `from generation.prompts import ...` 로 전환.
#
# 마이그레이션 순서:
# 1단계: _build_* 헬퍼 함수들 (의존성 없음)
# 2단계: _JOONGYEON_RULES, _REPORT_*_SYSTEM 상수
# 3단계: _system_* 빌더 함수들 (상수 의존)
