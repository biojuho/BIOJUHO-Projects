"""Ensure getdaytrends package root takes priority over workspace-level pythonpath.

When running from the workspace root, pytest.ini's ``pythonpath = .`` can cause
``from models import ...`` to resolve to biolinker/models.py instead of
getdaytrends/models.py.  This conftest inserts the getdaytrends directory at
sys.path[0] so local imports always win.
"""
import os
import sys


def pytest_configure(config):  # noqa: ARG001
    pkg_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    # Remove any existing entry first, then insert at front
    while pkg_root in sys.path:
        sys.path.remove(pkg_root)
    sys.path.insert(0, pkg_root)

    # loguru 기본 핸들러 제거 후 lambda sink 추가:
    # pytest stdout/stderr 캡처와 충돌로 발생하는
    # "ValueError: I/O operation on closed file" 방지.
    # StringIO 대신 lambda를 사용해 atexit flush 문제도 방지.
    try:
        from loguru import logger
        logger.remove()                                   # 기본 stderr 핸들러 제거
        logger.add(lambda _: None, level="WARNING")       # no-op null sink (pytest 안전)
    except ImportError:
        pass
