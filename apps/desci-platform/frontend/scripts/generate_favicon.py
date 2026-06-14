"""Generate the apple-touch-icon PNG from the DecentBio favicon motif.

Repo-owned, reproducible. Run:
    python scripts/generate_favicon.py
Outputs: public/apple-touch-icon.png (180x180)

The motif mirrors public/favicon.svg: a 3-node molecule in brand teal
(#20BB8A) on the dark navy app background (#040811).
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

SIZE = 180
BG = (4, 8, 17)          # #040811
ACCENT = (32, 187, 138)  # #20BB8A

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "public", "apple-touch-icon.png"))

# Supersample for crisp anti-aliased edges, then downscale.
SCALE = 4
S = SIZE * SCALE


def n(x: float) -> float:
    """Scale a 32-unit SVG coord to the supersampled canvas."""
    return x / 32 * S


def main() -> None:
    img = Image.new("RGB", (S, S), BG)
    draw = ImageDraw.Draw(img)

    nodes = [(16, 9), (10, 21), (22, 21)]
    bonds = [(0, 1), (0, 2), (1, 2)]
    bond_w = int(n(2.2))
    r = n(3.4)

    for a, b in bonds:
        draw.line([n(nodes[a][0]), n(nodes[a][1]), n(nodes[b][0]), n(nodes[b][1])],
                  fill=ACCENT, width=bond_w)
    # Round the bond joins.
    for x, y in nodes:
        draw.ellipse([n(x) - bond_w / 2, n(y) - bond_w / 2,
                      n(x) + bond_w / 2, n(y) + bond_w / 2], fill=ACCENT)
    for x, y in nodes:
        draw.ellipse([n(x) - r, n(y) - r, n(x) + r, n(y) + r], fill=ACCENT)
    # Inner cut on the top node to echo the SVG.
    cx, cy, cr = n(16), n(9), n(1.3)
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=BG)

    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main()
