import asyncio
import os
import sys

# Apply workaround for Windows asyncio ProactorEventLoop issues if needed
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # Fix encoding for Windows console
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "desci-platform", "biolinker")))

from dotenv import load_dotenv
from services.agent_service import get_agent_service

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "desci-platform", "biolinker", ".env"))


async def test_deep_research():
    print("\n[Test] Deep Research Skill")
    print("Step 1: Get Agent Service")
    service = get_agent_service()

    # Mock LLM if no key present (Optional, but assuming keys are set in environment)
    # For this test, we hope logic works.

    topic = "What is Agentic AI?"
    print(f"Topic: {topic}")

    try:
        # We limit search to avoid long waits or auth issues if search fails
        print("Step 2: Calling perform_deep_research...")
        result = await service.perform_deep_research(topic)
        print("Step 3: Research Complete")
        print("Result Keys:", result.keys())
        print("Queries Generated:", result.get("queries"))
        print("Report Length:", len(result.get("report", "")))
        print("Sources:", result.get("sources"))
    except Exception as e:
        print(f"Deep Research Failed: {e}")


async def test_content_publisher():
    print("\n[Test] Content Publisher Skill")
    service = get_agent_service()

    topic = "Agentic AI"
    raw_text = "Agentic AI refers to AI systems that can pursue complex goals with limited direct supervision..."

    formats = ["blog_post", "newsletter", "social_media"]

    for fmt in formats:
        print(f"\n--- Testing Format: {fmt} ---")
        try:
            content = await service.write_content(topic, raw_text, fmt)
            print(f"Content Preview ({len(content)} chars):\n{content[:200]}...")
        except Exception as e:
            print(f"Content Gen Failed: {e}")


async def main():
    print("Initializing Services...")
    # Initialize singleton
    get_agent_service()

    await test_deep_research()
    await test_content_publisher()


if __name__ == "__main__":
    asyncio.run(main())
