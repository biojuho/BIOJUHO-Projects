from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
backend_path = str(BACKEND_DIR)

if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from database import verify_database_connection


def main() -> int:
    verify_database_connection()
    print("database-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
