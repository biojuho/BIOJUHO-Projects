"""shared.llm.tool_schema - Pydantic-based tool definition and schema validation.

Inspired by GiniGen SiteAgent's Zod-to-OpenAI tool conversion.
Provides type-safe tool definitions using Pydantic models that
auto-convert to OpenAI function calling format.

Usage:
    from pydantic import BaseModel, Field
    from shared.llm.tool_schema import ToolDefinition

    class WeatherInput(BaseModel):
        city: str = Field(description="도시 이름")
        unit: str = Field(default="celsius", description="온도 단위")

    def get_weather(args: WeatherInput) -> str:
        return f"{args.city}의 날씨: 맑음 25°{args.unit[0].upper()}"

    weather_tool = ToolDefinition(
        name="get_weather",
        description="주어진 도시의 현재 날씨를 조회합니다.",
        input_schema=WeatherInput,
        execute=get_weather,
    )

    # Convert to OpenAI format
    openai_tool = weather_tool.to_openai_tool()

    # Validate and execute
    result = weather_tool.validate_and_execute({"city": "서울"})
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

LOGGER_NAME = "shared.llm"
log = logging.getLogger(LOGGER_NAME)
PYDANTIC_SCHEMA_TITLE_KEY = "title"
OPENAI_TOOL_TYPE_KEY = "type"
OPENAI_TOOL_FUNCTION_KEY = "function"
OPENAI_FUNCTION_NAME_KEY = "name"
OPENAI_FUNCTION_DESCRIPTION_KEY = "description"
OPENAI_FUNCTION_PARAMETERS_KEY = "parameters"
OPENAI_TOOL_TYPE_VALUE = "function"
VALIDATION_ERROR_TYPE_KEY = "type"
VALIDATION_ERROR_MESSAGE_KEY = "msg"
JSON_PARSE_ERROR_TYPE = "json_parse_error"
LOG_TOOL_VALIDATION_FAILED = "Tool validation failed: %s"
LOG_TOOL_EXECUTION_FAILED = "Tool execution failed: %s: %s"
LOG_TOOL_REGISTERED = "Registered tool: %s"
EXECUTION_ERROR_MESSAGE = "Execution error: {error}"
UNKNOWN_TOOL_MESSAGE = "Unknown tool: {name}"
VALIDATION_FAILED_MESSAGE = "Validation failed for tool '{tool_name}': {errors_json}"


class ToolValidationError(Exception):
    """Raised when tool argument validation fails."""

    def __init__(self, tool_name: str, errors: list[dict]) -> None:
        self.tool_name = tool_name
        self.errors = errors
        super().__init__(
            VALIDATION_FAILED_MESSAGE.format(
                tool_name=tool_name,
                errors_json=json.dumps(errors, ensure_ascii=False),
            )
        )


@dataclass
class ToolResult:
    """Result of a tool execution."""

    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None


class ToolDefinition:
    """Type-safe tool definition with Pydantic schema validation.

    Supports:
    - Pydantic model → OpenAI function calling format
    - Runtime argument validation
    - Structured error reporting
    """

    def __init__(
        self,
        *,
        name: str,
        description: str,
        input_schema: type[BaseModel],
        execute: Callable[..., Any],
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.execute = execute

    def _openai_parameters_schema(self) -> dict[str, Any]:
        schema = self.input_schema.model_json_schema()
        # Clean up Pydantic metadata that OpenAI doesn't need
        schema.pop(PYDANTIC_SCHEMA_TITLE_KEY, None)
        return schema

    def to_openai_tool(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format.

        Returns a dict compatible with OpenAI's `tools` parameter:
        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": { ... JSON Schema ... }
            }
        }
        """
        return {
            OPENAI_TOOL_TYPE_KEY: OPENAI_TOOL_TYPE_VALUE,
            OPENAI_TOOL_FUNCTION_KEY: {
                OPENAI_FUNCTION_NAME_KEY: self.name,
                OPENAI_FUNCTION_DESCRIPTION_KEY: self.description,
                OPENAI_FUNCTION_PARAMETERS_KEY: self._openai_parameters_schema(),
            },
        }

    def validate_args(self, raw_args: dict[str, Any] | str) -> BaseModel:
        """Validate raw arguments against the Pydantic schema.

        Args:
            raw_args: Dict or JSON string of arguments.

        Returns:
            Validated Pydantic model instance.

        Raises:
            ToolValidationError: If validation fails.
        """
        if isinstance(raw_args, str):
            try:
                raw_args = json.loads(raw_args)
            except json.JSONDecodeError as e:
                raise ToolValidationError(
                    self.name,
                    [
                        {
                            VALIDATION_ERROR_TYPE_KEY: JSON_PARSE_ERROR_TYPE,
                            VALIDATION_ERROR_MESSAGE_KEY: str(e),
                        }
                    ],
                ) from e

        try:
            return self.input_schema.model_validate(raw_args)
        except ValidationError as e:
            raise ToolValidationError(
                self.name,
                e.errors(),
            ) from e

    def validate_and_execute(self, raw_args: dict[str, Any] | str) -> ToolResult:
        """Validate arguments and execute the tool.

        Returns:
            ToolResult with success/failure status and output.
        """
        try:
            validated = self.validate_args(raw_args)
            result = self.execute(validated)
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=result,
            )
        except ToolValidationError as e:
            log.warning(LOG_TOOL_VALIDATION_FAILED, e)
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(e),
            )
        except Exception as e:
            log.error(LOG_TOOL_EXECUTION_FAILED, self.name, e)
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=EXECUTION_ERROR_MESSAGE.format(error=e),
            )

    def __repr__(self) -> str:
        return f"ToolDefinition(name={self.name!r})"


class ToolRegistry:
    """Registry for managing multiple tool definitions.

    Provides batch conversion to OpenAI format and tool dispatch.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        self._tools[tool.name] = tool
        log.debug(LOG_TOOL_REGISTERED, tool.name)

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """Convert all registered tools to OpenAI format."""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    def dispatch(self, name: str, raw_args: dict[str, Any] | str) -> ToolResult:
        """Find and execute a tool by name.

        Returns:
            ToolResult with success/failure.
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                tool_name=name,
                success=False,
                error=UNKNOWN_TOOL_MESSAGE.format(name=name),
            )
        return tool.validate_and_execute(raw_args)

    @property
    def tool_names(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={self.tool_names})"
