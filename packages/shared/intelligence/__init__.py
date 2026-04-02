"""shared.intelligence — cross-pipeline intelligence utilities."""
from .topic_bridge import TopicBridge, get_default_bridge, get_economic_context, get_score_boost

__all__ = [
    "TopicBridge",
    "get_default_bridge",
    "get_economic_context",
    "get_score_boost",
]
