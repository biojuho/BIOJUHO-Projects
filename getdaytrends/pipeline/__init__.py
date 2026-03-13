"""pipeline/ — Pipeline orchestration package for getdaytrends.

Phase 2 리펙토링: main.py(1308줄)에서 추출된 파이프라인 패키지.

현재 구조 (점진적 마이그레이션):
- main.py: 기존 모놀리식 파일 (파이프라인 + CLI + 스케줄러 포함)
- pipeline/: 새 패키지 (main.py의 파이프라인 함수를 re-export)

향후 마이그레이션:
1. 파이프라인 스텝들을 pipeline/ 하위 모듈로 이동
2. main.py는 CLI + 스케줄러 루프만 남김 (~100줄)
3. 외부 코드는 `from pipeline import run_pipeline` 로 전환
"""

# Phase 2: main.py의 핵심 파이프라인 함수를 re-export
# main.py는 __name__ == "__main__" 블록이 있어 직접 import하면
# 부작용이 있을 수 있으므로, 필요한 함수만 lazy import합니다.


def run_pipeline(*args, **kwargs):
    """main.py의 run_pipeline 래퍼 (lazy import)."""
    from main import run_pipeline as _run
    return _run(*args, **kwargs)


def run_single(*args, **kwargs):
    """main.py의 run_single 래퍼 (lazy import)."""
    from main import run_single as _run
    return _run(*args, **kwargs)


__all__ = ["run_pipeline", "run_single"]
