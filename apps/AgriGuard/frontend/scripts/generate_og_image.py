"""Generate the social-share OG image (1200x630) for AgriGuard.

Repo-owned, reproducible. Run:
    python scripts/generate_og_image.py
Outputs: public/og-image.png

Brand: dark farm-green bg, accent #4ade80 (theme-color), shield + sprout motif.
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG = (11, 31, 18)        # #0b1f12 deep farm green
ACCENT = (74, 222, 128)  # #4ade80
WHITE = (240, 248, 242)
MUTED = (150, 180, 160)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "public", "og-image.png"))


def load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for name in candidates:
        for base in (r"C:\Windows\Fonts", "/usr/share/fonts", ""):
            path = os.path.join(base, name) if base else name
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Subtle gradient toward a lighter green at the bottom.
    bottom = (16, 42, 26)
    for y in range(H):
        t = y / H
        col = tuple(int(BG[i] + (bottom[i] - BG[i]) * t) for i in range(3))
        draw.line([(0, y), (W, y)], fill=col)

    draw.rectangle([0, 0, 10, H], fill=ACCENT)

    eyebrow = load_font(["seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 30)
    draw.ellipse([80, 96, 104, 120], fill=ACCENT)
    draw.text((118, 92), "IoT · Blockchain · Smart Farm", font=eyebrow, fill=ACCENT)

    title_font = load_font(["seguibl.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 104)
    draw.text((78, 168), "AgriGuard", font=title_font, fill=WHITE)

    sub_font = load_font(["malgunbd.ttf", "malgun.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 44)
    draw.text((80, 312), "IoT 기반 스마트 농장 모니터링과", font=sub_font, fill=WHITE)
    draw.text((80, 372), "블록체인 이력추적 플랫폼", font=sub_font, fill=WHITE)

    chip_font = load_font(["malgun.ttf", "arial.ttf", "DejaVuSans.ttf"], 28)
    chips = ["실시간 센서 모니터링", "이상 탐지 알림", "공급망 이력추적"]
    x = 80
    y = 478
    for chip in chips:
        bbox = draw.textbbox((0, 0), chip, font=chip_font)
        tw = bbox[2] - bbox[0]
        pad = 22
        draw.rounded_rectangle(
            [x, y, x + tw + pad * 2, y + 56], radius=28,
            outline=ACCENT, width=2,
        )
        draw.text((x + pad, y + 12), chip, font=chip_font, fill=MUTED)
        x += tw + pad * 2 + 18

    foot_font = load_font(["seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 30)
    draw.text((80, 568), "Smart Farm Guardian", font=foot_font, fill=ACCENT)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main()
