import sys
import os

# Add the current directory to sys.path to ensure we can import the package if needed, 
# but we will run with venv python which has site-packages.
# We need to import the internal client. 
# Since notebooklm_mcp.server is the module, we can try importing from there.

try:
    from notebooklm_mcp.server import get_client
    
    print("[INFO] Attempting to get NotebookLM client...")
    client = get_client()
    
    print("[INFO] Fetching notebook list...")
    notebooks = client.list_notebooks()
    
    print(f"\n[FOUND] Found {len(notebooks)} notebooks:")
    for nb in notebooks:
        # Safe print for Windows console
        safe_title = nb.title.encode('cp949', errors='replace').decode('cp949')
        print(f"- {safe_title}")
        print(f"  ID: {nb.id}")
        print(f"  Sources: {nb.source_count}")
        print(f"  URL: {nb.url}")
        print("-" * 20)
        
except Exception as e:
    print(f"[ERROR] Failed to list notebooks: {e}")
    # Print more details if possible
    import traceback
    traceback.print_exc()
