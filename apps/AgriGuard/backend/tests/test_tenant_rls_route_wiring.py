from __future__ import annotations

import ast
from pathlib import Path

ROUTERS_DIR = Path(__file__).resolve().parents[1] / "routers"
TENANT_RLS_ROUTERS = [
    "products.py",
    "qr_tokens_admin.py",
    "sensor_devices_admin.py",
]


def _depends_targets(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    targets: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "Depends":
            continue
        if node.args and isinstance(node.args[0], ast.Name):
            targets.append(node.args[0].id)
    return targets


def test_authenticated_tenant_routers_use_tenant_rls_dependency():
    for router_file in TENANT_RLS_ROUTERS:
        targets = _depends_targets(ROUTERS_DIR / router_file)

        assert "get_tenant_rls_db" in targets
        assert "get_db" not in targets
