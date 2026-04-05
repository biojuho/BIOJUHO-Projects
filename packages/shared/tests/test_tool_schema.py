"""Unit tests for shared.llm.tool_schema — Pydantic-based tool validation & dispatch.

If tool_schema is broken:
  - Invalid LLM function call args execute without validation → data corruption
  - Valid args rejected → tool calls silently fail
  - Registry dispatch to unknown tool crashes instead of returning error

Run:
  python -m pytest shared/tests/test_tool_schema.py -v
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from shared.llm.tool_schema import (
    ToolDefinition,
    ToolRegistry,
    ToolResult,
    ToolValidationError,
)


# ---------------------------------------------------------------------------
# Test schemas
# ---------------------------------------------------------------------------


class WeatherInput(BaseModel):
    city: str = Field(description="City name")
    unit: str = Field(default="celsius", description="Temperature unit")


class SearchInput(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=10, ge=1, le=100)


def _weather_handler(args: WeatherInput) -> str:
    return f"{args.city}: 25°{args.unit[0].upper()}"


def _search_handler(args: SearchInput) -> dict:
    return {"query": args.query, "results": args.max_results}


def _crashing_handler(args: WeatherInput) -> str:
    raise RuntimeError("Handler exploded")


# ===========================================================================
# 1. ToolDefinition.to_openai_tool
# ===========================================================================


class TestToOpenAITool:

    def test_basic_structure(self):
        tool = ToolDefinition(
            name="get_weather",
            description="도시 날씨 조회",
            input_schema=WeatherInput,
            execute=_weather_handler,
        )
        result = tool.to_openai_tool()

        assert result["type"] == "function"
        assert result["function"]["name"] == "get_weather"
        assert result["function"]["description"] == "도시 날씨 조회"
        assert "parameters" in result["function"]

    def test_schema_contains_properties(self):
        tool = ToolDefinition(
            name="get_weather",
            description="test",
            input_schema=WeatherInput,
            execute=_weather_handler,
        )
        params = tool.to_openai_tool()["function"]["parameters"]
        assert "city" in params["properties"]
        assert "unit" in params["properties"]

    def test_title_stripped_from_schema(self):
        """Pydantic adds 'title' field — OpenAI doesn't need it."""
        tool = ToolDefinition(
            name="test", description="test",
            input_schema=WeatherInput, execute=_weather_handler,
        )
        params = tool.to_openai_tool()["function"]["parameters"]
        assert "title" not in params


# ===========================================================================
# 2. ToolDefinition.validate_args
# ===========================================================================


class TestValidateArgs:

    def test_valid_dict_args(self):
        tool = ToolDefinition(
            name="get_weather", description="test",
            input_schema=WeatherInput, execute=_weather_handler,
        )
        validated = tool.validate_args({"city": "Seoul"})
        assert isinstance(validated, WeatherInput)
        assert validated.city == "Seoul"
        assert validated.unit == "celsius"  # default

    def test_valid_json_string_args(self):
        tool = ToolDefinition(
            name="get_weather", description="test",
            input_schema=WeatherInput, execute=_weather_handler,
        )
        validated = tool.validate_args('{"city": "Tokyo", "unit": "fahrenheit"}')
        assert validated.city == "Tokyo"
        assert validated.unit == "fahrenheit"

    def test_invalid_json_raises_validation_error(self):
        tool = ToolDefinition(
            name="get_weather", description="test",
            input_schema=WeatherInput, execute=_weather_handler,
        )
        with pytest.raises(ToolValidationError) as exc_info:
            tool.validate_args("{invalid json}")
        assert exc_info.value.tool_name == "get_weather"
        assert any(e["type"] == "json_parse_error" for e in exc_info.value.errors)

    def test_missing_required_field_raises(self):
        tool = ToolDefinition(
            name="get_weather", description="test",
            input_schema=WeatherInput, execute=_weather_handler,
        )
        with pytest.raises(ToolValidationError):
            tool.validate_args({})  # 'city' is required

    def test_constraint_violation_raises(self):
        tool = ToolDefinition(
            name="search", description="test",
            input_schema=SearchInput, execute=_search_handler,
        )
        with pytest.raises(ToolValidationError):
            tool.validate_args({"query": "test", "max_results": 200})  # max 100


# ===========================================================================
# 3. ToolDefinition.validate_and_execute
# ===========================================================================


class TestValidateAndExecute:

    def test_successful_execution(self):
        tool = ToolDefinition(
            name="get_weather", description="test",
            input_schema=WeatherInput, execute=_weather_handler,
        )
        result = tool.validate_and_execute({"city": "Seoul"})
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.output == "Seoul: 25°C"
        assert result.error is None

    def test_validation_failure_returns_error_result(self):
        tool = ToolDefinition(
            name="get_weather", description="test",
            input_schema=WeatherInput, execute=_weather_handler,
        )
        result = tool.validate_and_execute({})  # missing 'city'
        assert result.success is False
        assert result.error is not None
        assert "get_weather" in result.error

    def test_execution_failure_returns_error_result(self):
        tool = ToolDefinition(
            name="crash", description="test",
            input_schema=WeatherInput, execute=_crashing_handler,
        )
        result = tool.validate_and_execute({"city": "Seoul"})
        assert result.success is False
        assert "Execution error" in result.error  # type: ignore

    def test_json_string_execution(self):
        tool = ToolDefinition(
            name="search", description="test",
            input_schema=SearchInput, execute=_search_handler,
        )
        result = tool.validate_and_execute('{"query": "AI trends", "max_results": 5}')
        assert result.success is True
        assert result.output == {"query": "AI trends", "results": 5}


# ===========================================================================
# 4. ToolRegistry
# ===========================================================================


class TestToolRegistry:

    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = ToolDefinition(
            name="weather", description="test",
            input_schema=WeatherInput, execute=_weather_handler,
        )
        registry.register(tool)
        assert registry.get("weather") is tool

    def test_get_unknown_returns_none(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_tool_names(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="weather", description="w",
            input_schema=WeatherInput, execute=_weather_handler,
        ))
        registry.register(ToolDefinition(
            name="search", description="s",
            input_schema=SearchInput, execute=_search_handler,
        ))
        assert set(registry.tool_names) == {"weather", "search"}
        assert len(registry) == 2

    def test_to_openai_tools(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="weather", description="w",
            input_schema=WeatherInput, execute=_weather_handler,
        ))
        registry.register(ToolDefinition(
            name="search", description="s",
            input_schema=SearchInput, execute=_search_handler,
        ))
        tools = registry.to_openai_tools()
        assert len(tools) == 2
        assert all(t["type"] == "function" for t in tools)

    def test_dispatch_known_tool(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="weather", description="w",
            input_schema=WeatherInput, execute=_weather_handler,
        ))
        result = registry.dispatch("weather", {"city": "Seoul"})
        assert result.success is True
        assert result.output == "Seoul: 25°C"

    def test_dispatch_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.dispatch("nonexistent", {"arg": "val"})
        assert result.success is False
        assert "Unknown tool" in result.error  # type: ignore

    def test_dispatch_with_validation_error(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="search", description="s",
            input_schema=SearchInput, execute=_search_handler,
        ))
        result = registry.dispatch("search", {"max_results": 5})  # missing 'query'
        assert result.success is False

    def test_repr(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="weather", description="w",
            input_schema=WeatherInput, execute=_weather_handler,
        ))
        assert "weather" in repr(registry)

    def test_empty_registry(self):
        registry = ToolRegistry()
        assert len(registry) == 0
        assert registry.tool_names == []
        assert registry.to_openai_tools() == []


# ===========================================================================
# 5. ToolDefinition repr
# ===========================================================================


class TestRepr:

    def test_tool_repr(self):
        tool = ToolDefinition(
            name="my_tool", description="test",
            input_schema=WeatherInput, execute=_weather_handler,
        )
        assert "my_tool" in repr(tool)
