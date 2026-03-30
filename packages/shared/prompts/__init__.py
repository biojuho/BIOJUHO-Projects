"""shared.prompts — Centralized prompt template library.

Usage::
    from shared.prompts import PromptManager
    pm = PromptManager()
    system = pm.render("content_generation", category="Tech", locale="ko-KR")
"""
from shared.prompts.manager import PromptManager, get_prompt_manager

__all__ = ["PromptManager", "get_prompt_manager"]
