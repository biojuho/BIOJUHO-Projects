"""
getdaytrends/embeddings.py — shared.embeddings 래퍼 (하위 호환성 유지).

v14.0: 독립 모듈 → shared/embeddings로 이전.
이 파일은 기존 import를 깨지 않기 위한 호환 래퍼입니다.
"""

import sys
from pathlib import Path

# shared 모듈 경로 보장
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.embeddings import (  # noqa: E402, F401
    compute_similarity_matrix,
    cosine_similarity,
    deduplicate_texts,
    embed_texts,
    embed_texts_async,
)

__all__ = [
    "embed_texts",
    "embed_texts_async",
    "cosine_similarity",
    "compute_similarity_matrix",
    "deduplicate_texts",
]
