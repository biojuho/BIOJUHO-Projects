"""Generate the social-share OG image (1200x630) for DecentBio.

Repo-owned, reproducible asset generator. Run:
    python scripts/generate-og-image.mjs.py
Outputs: public/og-image.png

Brand: bg #040811 (theme-color), accent #20BB8A (--primary HSL 161 71% 43%).
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG = (4, 8, 17)        # #040811
ACCENT = (32, 187, 138)  # #20BB8A
WHITE = (240, 244, 248)
MUTED = (150, 165, 180)

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

    # Subtle vertical gradient toward a slightly lighter navy at the bottom.
    top = BG
    bottom = (10, 18, 32)
    for y in range(H):
        t = y / H
        col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (W, y)], fill=col)

    # Accent rule on the left edge.
    draw.rectangle([0, 0, 10, H], fill=ACCENT)

    # Accent dot + eyebrow.
    eyebrow = load_font(["seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 30)
    draw.ellipse([80, 96, 104, 120], fill=ACCENT)
    draw.text((118, 92), "DeSci · AI · Blockchain", font=eyebrow, fill=ACCENT)

    # Wordmark.
    title_font = load_font(["seguibl.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 104)
    draw.text((78, 168), "DecentBio", font=title_font, fill=WHITE)

    # Tagline (Korean-first, the primary audience).
    sub_font = load_font(["malgunbd.ttf", "malgun.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 44)
    draw.text((80, 312), "바이오 연구를 AI로 가속화하는", font=sub_font, fill=WHITE)
    draw.text((80, 372), "탈중앙 사이언스 플랫폼", font=sub_font, fill=WHITE)

    # Feature chips.
    chip_font = load_font(["malgun.ttf", "arial.ttf", "DejaVuSans.ttf"], 28)
    chips = ["정부과제 매칭", "VC 연결", "AI 제안서", "IPFS 논문 저장"]
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

    # Domain footer.
    foot_font = load_font(["seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 30)
    draw.text((80, 568), "decentbio.xyz", font=foot_font, fill=ACCENT)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main()
