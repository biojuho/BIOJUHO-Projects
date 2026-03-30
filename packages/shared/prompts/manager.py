"""
shared.prompts.manager — YAML-based prompt template manager.

Loads prompt templates from YAML files, supports variable substitution,
few-shot example injection, versioning, and locale-aware rendering.

Templates live in ``shared/prompts/templates/*.yaml`` with this schema::

    name: content_generation
    version: 1
    description: General content generation prompt
    system: |
      You are a {role}.
      Locale: {locale}
      {constraints}
    variables:
      role: "professional content analyst"
      locale: "ko-KR"
      constraints: ""
    few_shot_key: ""
    tags: [content, generation]

Few-shot examples live in ``shared/prompts/few_shot_examples/*.json``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_EXAMPLES_DIR = Path(__file__).parent / "few_shot_examples"

try:
    import yaml as _yaml
    _YAML_OK = True
except ImportError:
    _YAML_OK = False


def _load_yaml(path: Path) -> dict:
    if not _YAML_OK:
        raise ImportError("PyYAML is required: pip install pyyaml")
    with open(path, encoding="utf-8") as f:
        return _yaml.safe_load(f) or {}


class PromptTemplate:
    """A single loaded prompt template."""

    __slots__ = ("name", "version", "description", "system", "variables",
                 "few_shot_key", "tags", "source_path")

    def __init__(self, data: dict, source_path: Path | None = None):
        self.name: str = data["name"]
        self.version: int = data.get("version", 1)
        self.description: str = data.get("description", "")
        self.system: str = data["system"]
        self.variables: dict[str, str] = data.get("variables", {})
        self.few_shot_key: str = data.get("few_shot_key", "")
        self.tags: list[str] = data.get("tags", [])
        self.source_path = source_path

    def render(self, few_shot_text: str = "", **overrides: str) -> str:
        """Render the system prompt with variable substitution."""
        merged = {**self.variables, **overrides}
        merged.setdefault("few_shot_examples", few_shot_text)
        try:
            return self.system.format_map(_SafeDict(merged))
        except (KeyError, ValueError) as exc:
            log.warning("Prompt render error for %s: %s", self.name, exc)
            return self.system


class _SafeDict(dict):
    """Dict that returns {key} for missing keys instead of raising."""
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class PromptManager:
    """Central prompt template manager.

    Loads all YAML templates from the templates directory and JSON
    few-shot examples from the examples directory.
    """

    def __init__(
        self,
        templates_dir: Path | str | None = None,
        examples_dir: Path | str | None = None,
    ):
        self._templates_dir = Path(templates_dir) if templates_dir else _TEMPLATES_DIR
        self._examples_dir = Path(examples_dir) if examples_dir else _EXAMPLES_DIR
        self._templates: dict[str, PromptTemplate] = {}
        self._examples: dict[str, list[dict]] = {}
        self._load_all()

    def _load_all(self) -> None:
        self._load_templates()
        self._load_examples()

    def _load_templates(self) -> None:
        if not self._templates_dir.is_dir():
            log.debug("Templates dir not found: %s", self._templates_dir)
            return
        for path in sorted(self._templates_dir.glob("*.yaml")):
            try:
                data = _load_yaml(path)
                tpl = PromptTemplate(data, source_path=path)
                self._templates[tpl.name] = tpl
            except Exception as exc:
                log.warning("Failed to load template %s: %s", path.name, exc)

    def _load_examples(self) -> None:
        if not self._examples_dir.is_dir():
            return
        for path in sorted(self._examples_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                key = path.stem
                self._examples[key] = data if isinstance(data, list) else [data]
            except Exception as exc:
                log.warning("Failed to load examples %s: %s", path.name, exc)

    def list_templates(self) -> list[str]:
        return sorted(self._templates.keys())

    def get_template(self, name: str) -> PromptTemplate | None:
        return self._templates.get(name)

    def render(self, template_name: str, **kwargs: str) -> str:
        """Render a template by name with variable overrides.

        Returns the rendered system prompt string.
        Raises KeyError if template not found.
        """
        tpl = self._templates.get(template_name)
        if tpl is None:
            raise KeyError(f"Prompt template '{template_name}' not found. "
                           f"Available: {self.list_templates()}")

        few_shot_text = ""
        fs_key = kwargs.pop("few_shot_key", "") or tpl.few_shot_key
        if fs_key and fs_key in self._examples:
            examples = self._examples[fs_key]
            few_shot_text = self._format_few_shot(examples)

        return tpl.render(few_shot_text=few_shot_text, **kwargs)

    @staticmethod
    def _format_few_shot(examples: list[dict]) -> str:
        parts = []
        for i, ex in enumerate(examples, 1):
            inp = ex.get("input", ex.get("query", ""))
            out = ex.get("output", ex.get("response", ""))
            parts.append(f"Example {i}:\nInput: {inp}\nOutput: {out}")
        return "\n\n".join(parts)

    def register(self, data: dict) -> None:
        """Register a template from a dict (for programmatic use)."""
        tpl = PromptTemplate(data)
        self._templates[tpl.name] = tpl

    def get_few_shot(self, key: str) -> list[dict]:
        return self._examples.get(key, [])


_manager: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    """Return the singleton PromptManager instance."""
    global _manager
    if _manager is None:
        _manager = PromptManager()
    return _manager
