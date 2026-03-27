"""Project-specific prompt template manager.

Loads YAML templates from the ``templates/`` directory and builds
LLM prompts with project-specific tone, style, audience, and structure.

Usage:
    from notebooklm_automation.templates import PromptTemplateManager

    mgr = PromptTemplateManager()
    prompt = mgr.build_article_prompt("프로젝트A", extracted_text)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger as log

_TEMPLATES_DIR = Path(__file__).parent


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file. Falls back to a basic parser if PyYAML missing."""
    try:
        import yaml

        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Simple fallback parser for key: value lines
        result: dict[str, Any] = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or not line or ":" not in line:
                    continue
                key, _, value = line.partition(":")
                value = value.strip().strip('"').strip("'")
                if value:
                    result[key.strip()] = value
        return result


class PromptTemplateManager:
    """Manage per-project prompt templates."""

    def __init__(self, templates_dir: str | Path | None = None):
        self._dir = Path(templates_dir) if templates_dir else _TEMPLATES_DIR
        self._cache: dict[str, dict[str, Any]] = {}

    def _load(self, project: str) -> dict[str, Any]:
        """Load template for a project, falling back to _default."""
        if project in self._cache:
            return self._cache[project]

        # Try project-specific template
        project_file = self._dir / f"{project}.yaml"
        default_file = self._dir / "_default.yaml"

        default_cfg = _load_yaml(default_file) if default_file.exists() else {}

        if project_file.exists():
            project_cfg = _load_yaml(project_file)
            merged = {**default_cfg, **project_cfg}
            log.info("[Template] loaded project template: %s", project)
        else:
            merged = default_cfg
            log.debug("[Template] using default template for: %s", project or "(none)")

        self._cache[project] = merged
        return merged

    def build_article_prompt(self, project: str, content: str) -> str:
        """Build a complete article generation prompt.

        Returns a prompt string with project-specific instructions
        injected into the system template.
        """
        cfg = self._load(project)

        tone = cfg.get("tone", "전문적이면서 읽기 쉬운")
        style = cfg.get("style", "인사이트 중심 블로그")
        audience = cfg.get("target_audience", "일반 독자")
        word_count = cfg.get("word_count", "1500~3000")
        language = cfg.get("language", "한국어")
        custom = cfg.get("custom_instructions", "")

        # Structure
        structure_items = cfg.get("structure", [])
        if isinstance(structure_items, list):
            structure_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(structure_items))
        else:
            structure_text = str(structure_items)

        # Format rules
        format_rules = cfg.get("format_rules", [])
        if isinstance(format_rules, list):
            rules_text = "\n".join(f"  - {r}" for r in format_rules)
        else:
            rules_text = str(format_rules)

        prompt = f"""당신은 {style} 전문 라이터입니다.
아래 자료를 바탕으로 {language} 블로그 아티클을 작성해주세요.

## 톤 & 스타일
- 톤: {tone}
- 대상: {audience}
- 분량: {word_count}자

## 글 구조
{structure_text}

## 포맷 규칙
{rules_text}
"""

        if custom:
            prompt += f"\n## 추가 지침\n{custom}\n"

        prompt += f"""
## 출력 형식
반드시 아래 JSON 형식으로 응답:
```json
{{
  "title": "아티클 제목",
  "body": "# 제목\\n\\n본문 내용...",
  "summary": "3줄 핵심 요약",
  "tags": ["태그1", "태그2"]
}}
```

## 입력 자료
{content[:8000]}"""

        return prompt

    def list_templates(self) -> list[str]:
        """List available template names."""
        templates: list[str] = []
        for f in sorted(self._dir.glob("*.yaml")):
            name = f.stem
            if name.startswith("_"):
                name = f"{name} (default)"
            templates.append(name)
        return templates
