# ruff: noqa: S101  pytest assertions are the test's purpose
"""Tests for the brand-asset generators.

Runs each generator and asserts it writes a valid PNG of the expected size,
locking the favicon/OG-image output so a regression in the drawing code is
caught. Requires Pillow (same dependency the generators use).
"""
from __future__ import annotations

import importlib.util
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.normpath(os.path.join(HERE, "..", "public"))


def _load(module_name: str):
    path = os.path.join(HERE, f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_og_image_writes_1200x630_png():
    _load("generate_og_image").main()
    path = os.path.join(PUBLIC, "og-image.png")
    assert os.path.exists(path)
    with Image.open(path) as img:
        assert img.format == "PNG"
        assert img.size == (1200, 630)


def test_generate_favicon_writes_expected_icon_sizes():
    _load("generate_favicon").main()
    expected = {
        "apple-touch-icon.png": (180, 180),
        "icon-192.png": (192, 192),
        "icon-512.png": (512, 512),
    }
    for name, size in expected.items():
        path = os.path.join(PUBLIC, name)
        assert os.path.exists(path), name
        with Image.open(path) as img:
            assert img.format == "PNG"
            assert img.size == size
