import os

with open("apps/AgriGuard/backend/main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

def write_router(filename, router_name, start_line, end_line, extra_imports=""):
    header = f'from fastapi import APIRouter, Depends, HTTPException, WebSocket\nfrom sqlalchemy.orm import Session\nfrom sqlalchemy.orm import selectinload\nfrom dependencies import get_db\nimport models\nimport schemas\nimport uuid\nimport json\nfrom datetime import UTC, datetime, timedelta\nfrom auth import get_current_user\nfrom services.chain_simulator import get_chain\n\n{extra_imports}\n\n{router_name} = APIRouter()\n\n'
    
    body_lines = lines[start_line-1:end_line]
    body = "".join(body_lines).replace("@app.", f"@{router_name}.")
    
    with open(f"apps/AgriGuard/backend/routers/{filename}", "w", encoding="utf-8") as out:
        out.write(header + body)

# We need the cache import in dashboard
cache_imports = "try:\n    from shared.cache import get_cache\nexcept ImportError:\n    pass # Handle fallback if needed, but dependencies might provide it\n\n"
cache_imports += "try:\n    from main import get_cache\nexcept:\n    pass\n"

write_router("dashboard.py", "router", 213, 334, cache_imports)
write_router("users.py", "router", 337, 351)
write_router("products.py", "router", 354, 479)
write_router("qr_events.py", "router", 481, 582)

# Iot needs its specific imports
iot_imports = "from iot_service import get_current_status, get_latest_readings, handle_ws_connection\n"
write_router("iot.py", "router", 585, 604, iot_imports)

print("Extracted routers.")
