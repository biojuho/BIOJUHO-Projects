"""
BioLinker - VC dataset loader.

Loads the curated Korean + global biotech VC dataset from
``backend/data/vcs_seed.json`` so the runtime, the Postgres seed
script, and the HTTP API all read the same source of truth.

The class name and ``fetch_vc_list`` signature are preserved so
existing consumers (smart_matcher, agent_graph, tests) do not change.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from models import VCFirm

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "vcs_seed.json"


@lru_cache(maxsize=1)
def _load_seed() -> list[VCFirm]:
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    return [VCFirm.model_validate(item) for item in raw]


class VCCrawler:
    """VC dataset accessor — backed by the curated JSON resource."""

    def fetch_vc_list(self) -> list[VCFirm]:
        """Return the full curated VC list (KR + global)."""
        return list(_load_seed())


_vc_crawler: VCCrawler | None = None


def get_vc_crawler() -> VCCrawler:
    global _vc_crawler
    if _vc_crawler is None:
        _vc_crawler = VCCrawler()
    return _vc_crawler
