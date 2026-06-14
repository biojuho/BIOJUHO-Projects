"""Generate raster icons from the DecentBio favicon motif.

Repo-owned, reproducible. Run:
    python scripts/generate_favicon.py
Outputs (in public/):
    apple-touch-icon.png  180x180  (iOS home screen)
    icon-192.png          192x192  (PWA manifest)
    icon-512.png          512x512  (PWA manifest / splash)

The motif mirrors public/favicon.svg: a 3-node molecule in brand teal
(#20BB8A) on the dark navy app background (#040811).
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

BG = (4, 8, 17)          # #040811
ACCENT = (32, 187, 138)  # #20BB8A
SUPERSAMPLE = 4

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.normpath(os.path.join(HERE, "..", "public"))

# (filename, pixel size). corner radius scales with size for the larger tiles.
TARGETS = [
    ("apple-touch-icon.png", 180),
    ("icon-192.png", 192),
    ("icon-512.png", 512),
]


def render(size: int) -> Image.Image:
    s = size * SUPERSAMPLE

    def n(x: float) -> float:
        """Scale a 32-unit SVG coord to the supersampled canvas."""
        return x / 32 * s

    img = Image.new("RGB", (s, s), BG)
    draw = ImageDraw.Draw(img)

    nodes = [(16, 9), (10, 21), (22, 21)]
    bonds = [(0, 1), (0, 2), (1, 2)]
    bond_w = int(n(2.2))
    r = n(3.4)

    for a, b in bonds:
        draw.line([n(nodes[a][0]), n(nodes[a][1]), n(nodes[b][0]), n(nodes[b][1])],
                  fill=ACCENT, width=bond_w)
    for x, y in nodes:  # round the bond joins
        draw.ellipse([n(x) - bond_w / 2, n(y) - bond_w / 2,
                      n(x) + bond_w / 2, n(y) + bond_w / 2], fill=ACCENT)
    for x, y in nodes:
        draw.ellipse([n(x) - r, n(y) - r, n(x) + r, n(y) + r], fill=ACCENT)
    cx, cy, cr = n(16), n(9), n(1.3)  # inner cut on the top node
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=BG)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    os.makedirs(PUBLIC, exist_ok=True)
    for name, size in TARGETS:
        out = os.path.join(PUBLIC, name)
        render(size).save(out, "PNG", optimize=True)
        print(f"wrote {out} ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main()
