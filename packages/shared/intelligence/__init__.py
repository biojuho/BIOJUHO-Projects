"""shared.intelligence — cross-pipeline intelligence utilities."""
from .topic_bridge import TopicBridge, get_default_bridge, get_economic_context, get_score_boost
from .code_graph import (
    CodeGraphStore,
    FileParseResult,
    GraphEdge,
    GraphNode,
    ImpactResult,
    PythonASTParser,
)
from .impact_analyzer import ChangeReport, ImpactAnalyzer

__all__ = [
    "TopicBridge",
    "get_default_bridge",
    "get_economic_context",
    "get_score_boost",
    # Phase 2: Code Graph & Impact Analysis
    "CodeGraphStore",
    "FileParseResult",
    "GraphEdge",
    "GraphNode",
    "ImpactResult",
    "PythonASTParser",
    "ChangeReport",
    "ImpactAnalyzer",
]
