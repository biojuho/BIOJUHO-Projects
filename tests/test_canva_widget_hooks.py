from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WIDGET_STATE_HOOK = PROJECT_ROOT / "mcp" / "canva-mcp" / "src" / "hooks" / "use-widget-state.ts"
OPENAI_GLOBAL_HOOK = PROJECT_ROOT / "mcp" / "canva-mcp" / "src" / "hooks" / "use-openai-global.ts"


def test_widget_state_preserves_default_until_host_state_exists() -> None:
    source = WIDGET_STATE_HOOK.read_text(encoding="utf-8")

    assert "if (widgetStateFromWindow != null)" in source
    assert "if (widgetStateFromWindow == null)" in source
    assert "return;" in source
    assert source.index("if (widgetStateFromWindow == null)") < source.index(
        "_setWidgetState(widgetStateFromWindow);"
    )


def test_openai_global_subscription_only_reacts_to_present_keys() -> None:
    source = OPENAI_GLOBAL_HOOK.read_text(encoding="utf-8")

    assert "const value = event.detail.globals[key];" in source
    assert "if (value === undefined)" in source
    assert "return;" in source
    assert "window.addEventListener(SET_GLOBALS_EVENT_TYPE" in source
