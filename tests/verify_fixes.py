import os
import sys
from unittest.mock import patch

# Add paths
sys.path.append(r"d:\AI 프로젝트\desci-platform")
sys.path.append(r"d:\AI 프로젝트\MCP_notion-antigravity\scripts")
sys.path.append(r"d:\AI 프로젝트\MCP_notion-antigravity")


def test_biolinker_warnings():
    print("\n--- Testing BioLinker Warnings ---")
    try:
        from biolinker.services.analyzer import RFPAnalyzer, RFPDocument, UserProfile
        from biolinker.services.vector_store import VectorStore

        # Test 1: Analyzer Mock Warning
        print("[Test] Analyzer Mock Result:")
        analyzer = RFPAnalyzer()
        rfp = RFPDocument(
            id="test", title="Test RFP", body_text="Test Body", source="Test Source", deadline=None, keywords=[]
        )
        # Fix: current_trl must be string
        profile = UserProfile(
            company_name="TestCorp",
            tech_keywords=["Bio"],
            tech_description="Bio Tech",
            company_size="Small",
            current_trl="3",
        )
        result = analyzer._generate_mock_result(rfp, profile)
        print(f"Match Summary: {result.match_summary}")

        if any("SIMULATION" in s for s in result.match_summary):
            print("[PASS] Simulation warning found in match summary.")
        else:
            print("[FAIL] No simulation warning found.")

        # Test 2: VectorStore Mock Warning
        print("\n[Test] VectorStore Mock Embedding:")
        store = VectorStore()
        # Trigger mock embedding
        embedding = store._get_embedding("test text")
        print("[PASS] _get_embedding executed (check stdout for CRITICAL WARNING above).")

    except ImportError as e:
        print(f"[FAIL] Import Error: {e}")
    except Exception as e:
        print(f"[FAIL] Error: {e}")


def test_brain_json_parsing():
    print("\n--- Testing Brain Module JSON Parsing ---")
    try:
        from brain_module import BrainModule

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
            brain = BrainModule()

            # Case 1: Code Block
            text1 = 'Here is the json:\n```json\n{"key": "value"}\n```'
            res1 = brain._robust_json_parse(text1)
            if res1 == {"key": "value"}:
                print("[PASS] Code block parsing")
            else:
                print(f"[FAIL] Code block parsing. Got: {res1}")

            # Case 2: Trailing Comma
            text2 = '{"key": "value", }'
            res2 = brain._robust_json_parse(text2)
            if res2 == {"key": "value"}:
                print("[PASS] Trailing comma fixing")
            else:
                print(f"[FAIL] Trailing comma fixing. Got: {res2}")

    except Exception as e:
        print(f"[FAIL] Error: {e}")


def test_notion_server_env():
    print("\n--- Testing Notion Server Env Var ---")
    try:
        with open(r"d:\AI 프로젝트\MCP_notion-antigravity\server.py", encoding="utf-8") as f:
            content = f.read()
            if 'ANTIGRAVITY_DB_ID = os.getenv("ANTIGRAVITY_DB_ID")' in content:
                print("[PASS] Server uses os.getenv for DB ID")
            else:
                print("[FAIL] Server does not use os.getenv")
    except Exception as e:
        print(f"[FAIL] Error: {e}")


if __name__ == "__main__":
    try:
        # Force utf-8 for stdout/stderr just to be safe, though avoiding emojis is better
        sys.stdout.reconfigure(encoding="utf-8")
    except:
        pass

    test_biolinker_warnings()
    test_brain_json_parsing()
    test_notion_server_env()
