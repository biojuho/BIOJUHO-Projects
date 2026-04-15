import os
import sys
import traceback

# Ensure shared package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.llm.reasoning.vibe_graph import build_vibe_graph


def main():
    print("Initializing Vibe Coding LangGraph Architecture...")
    from langchain_openai import ChatOpenAI

    # Initialize the specific model via Ollama's OpenAI-compatible endpoint
    chat_model = ChatOpenAI(
        model="qwen2.5-coder:7b",
        api_key="ollama",
        base_url="http://localhost:11434/v1",
        max_tokens=4096,
        temperature=0.0,
    )

    # Build the graph
    app = build_vibe_graph(chat_model)

    # Run the graph
    print("Graph built successfully. Invoking...")

    # Note: Checkpointer needs a configuration dictionary to track the thread
    config = {"configurable": {"thread_id": "vibe_session_001"}}

    inputs = {
        "vibe_input": "빠르고 세련된 CRUD 앱 만들어줘",
        "messages": [],
        "todos": ["1. Setup frontend React app", "2. Create backend API for CRUD logic"],
        "retries": 0,
    }

    try:
        # We manually step through or invoke as stream to see progress
        for event in app.stream(inputs, config=config, stream_mode="values"):
            print("-" * 50)
            print("Current State Check:")
            for key, value in event.items():
                short_val = str(value)[:100] + ("..." if len(str(value)) > 100 else "")
                print(f"  {key}: {short_val}")
    except Exception as e:
        print(f"Error during graph execution: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
