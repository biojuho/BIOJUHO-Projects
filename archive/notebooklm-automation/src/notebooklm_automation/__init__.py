"""NotebookLM Automation — unified bridge, health, adapters & publishers."""

__version__ = "2.0.0"

from .alerts import AlertLevel, send_alert
from .config import NotebookLMConfig, get_config
from .execution_log import ExecutionLogger
from .extractors import extract_image_text, extract_pdf_text
from .publishers.notion import publish_to_notion

__all__ = [
    "AlertLevel",
    "ExecutionLogger",
    "NotebookLMConfig",
    "extract_image_text",
    "extract_pdf_text",
    "get_config",
    "publish_to_notion",
    "send_alert",
]
