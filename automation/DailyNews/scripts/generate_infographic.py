#!/usr/bin/env python3
"""
Antigravity Professional Infographic Generator v2
참고: 한국 스타일 인포그래픽 - 바 차트, 그리드 카드, 픽토그램, 큰 숫자
"""

import io
import os
from datetime import date

import matplotlib
from PIL import Image, ImageDraw, ImageFont

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Matplotlib 한글 폰트 설정
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

# 카테고리별 테마 (단색 기반)
THEMES = {
    "Tech": {"primary": "#2563EB", "light": "#DBEAFE", "dark": "#1E40AF", "icon": "💻", "name": "테크"},
    "Economy_KR": {"primary": "#059669", "light": "#D1FAE5", "dark": "#047857", "icon": "📈", "name": "한국경제"},
    "Economy_Global": {"primary": "#D97706", "light": "#FEF3C7", "dark": "#B45309", "icon": "🌍", "name": "글로벌경제"},
    "Crypto": {"primary": "#7C3AED", "light": "#EDE9FE", "dark": "#5B21B6", "icon": "₿", "name": "크립토"},
    "Global_Affairs": {"primary": "#DC2626", "light": "#FEE2E2", "dark": "#B91C1C", "icon": "🌐", "name": "국제정세"},
}


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def create_bar_chart_image(values, labels, color, width=500, height=200):
    """수평 바 차트 생성"""
    fig, ax = plt.subplots(figsize=(width / 100, height / 100), facecolor="white")
    ax.set_facecolor("white")

    y_pos = np.arange(len(labels))
    bars = ax.barh(y_pos, values, color=color, height=0.6, edgecolor="none")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=14, fontweight="bold")
    ax.set_xlim(0, max(values) * 1.3)
    ax.invert_yaxis()

    # 스타일 정리
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=False, bottom=False)
    ax.set_xticks([])

    # 값 표시
    for bar, val in zip(bars, values, strict=False):
        ax.text(
            bar.get_width() + 2,
            bar.get_y() + bar.get_height() / 2,
            f"{val}건",
            va="center",
            fontsize=12,
            fontweight="bold",
            color=color,
        )

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100, facecolor="white", edgecolor="none")
    buf.seek(0)
    plt.close(fig)
    return Image.open(buf)


def draw_stat_card(draw, x, y, width, height, number, label, color, fonts):
    """통계 카드 (큰 숫자 + 라벨)"""
    # 카드 배경
    draw.rounded_rectangle([x, y, x + width, y + height], radius=15, fill="white", outline=color, width=2)

    # 큰 숫자
    draw.text((x + width // 2, y + height // 2 - 10), str(number), font=fonts["big"], fill=color, anchor="mm")

    # 라벨
    draw.text((x + width // 2, y + height - 25), label, font=fonts["small"], fill="#666666", anchor="mm")


def draw_news_card(draw, x, y, width, height, number, text, color, fonts, icon="📰"):
    """뉴스 카드 (번호 + 아이콘 + 텍스트)"""
    # 카드 배경
    draw.rounded_rectangle([x, y, x + width, y + height], radius=10, fill="white", outline="#E5E7EB", width=1)

    # 번호 원
    circle_r = 18
    circle_x = x + 30
    circle_y = y + height // 2
    draw.ellipse([circle_x - circle_r, circle_y - circle_r, circle_x + circle_r, circle_y + circle_r], fill=color)
    draw.text((circle_x, circle_y), str(number), font=fonts["body"], fill="white", anchor="mm")

    # 아이콘
    draw.text((circle_x + 40, circle_y), icon, font=fonts["body"], fill=color, anchor="lm")

    # 텍스트
    short_text = text[:40] + ("..." if len(text) > 40 else "")
    draw.text((circle_x + 70, circle_y), short_text, font=fonts["body"], fill="#1F2937", anchor="lm")


def create_news_card(category: str, summary: list, insight: str, output_path: str):
    """프로페셔널 스타일 인포그래픽 생성"""

    # 캔버스 크기
    width, height = 800, 1200
    theme = THEMES.get(category, THEMES["Tech"])
    primary = theme["primary"]
    light = theme["light"]

    # 흰색 배경
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # 폰트 설정
    try:
        fonts = {
            "title": ImageFont.truetype("malgun.ttf", 36),
            "subtitle": ImageFont.truetype("malgun.ttf", 24),
            "body": ImageFont.truetype("malgun.ttf", 18),
            "small": ImageFont.truetype("malgun.ttf", 14),
            "big": ImageFont.truetype("malgun.ttf", 48),
        }
    except:
        default = ImageFont.load_default()
        fonts = {k: default for k in ["title", "subtitle", "body", "small", "big"]}

    y_pos = 0

    # ===== 헤더 영역 (색상 배경) =====
    header_height = 120
    draw.rectangle([0, 0, width, header_height], fill=primary)

    # 카테고리 아이콘 + 타이틀
    draw.text((40, 35), theme["icon"], font=fonts["title"], fill="white")
    draw.text((100, 40), f"{theme['name']} Daily Brief", font=fonts["title"], fill="white")

    # 날짜
    today = date.today().strftime("%Y.%m.%d")
    draw.text((width - 40, 50), today, font=fonts["subtitle"], fill="white", anchor="rm")

    y_pos = header_height + 30

    # ===== 핵심 뉴스 섹션 =====
    draw.rounded_rectangle([30, y_pos, width - 30, y_pos + 280], radius=15, fill=light)

    # 섹션 헤더
    draw.text((50, y_pos + 20), "📌 오늘의 핵심 뉴스", font=fonts["subtitle"], fill=theme["dark"])
    y_pos += 70

    # 뉴스별 아이콘
    news_icons = ["📌", "📊", "🔔"]

    # 뉴스 카드들
    for idx, point in enumerate(summary[:3], 1):
        icon = news_icons[idx - 1] if idx <= len(news_icons) else "📰"
        draw_news_card(draw, 50, y_pos, width - 100, 60, idx, point, primary, fonts, icon)
        y_pos += 70

    y_pos += 50

    # ===== 인사이트 섹션 =====
    draw.text((40, y_pos), "💡 쥬팍's 인사이트", font=fonts["subtitle"], fill="#1F2937")
    y_pos += 40

    # 인사이트 박스
    insight_height = 120
    draw.rounded_rectangle(
        [30, y_pos, width - 30, y_pos + insight_height], radius=15, fill="#F9FAFB", outline=primary, width=2
    )

    # 인사이트 텍스트
    insight_short = insight[:120] + ("..." if len(insight) > 120 else "")
    lines = [insight_short[i : i + 40] for i in range(0, len(insight_short), 40)]
    text_y = y_pos + 25
    for line in lines[:3]:
        draw.text((50, text_y), line, font=fonts["body"], fill="#374151")
        text_y += 28

    y_pos += insight_height + 40

    # ===== 바 차트 섹션 =====
    draw.text((40, y_pos), "📈 카테고리별 관심도", font=fonts["subtitle"], fill="#1F2937")
    y_pos += 50

    # 바 차트 생성 및 붙이기
    bar_values = [85, 72, 58]
    bar_labels = ["주요 이슈", "경제 영향", "시장 반응"]
    bar_chart = create_bar_chart_image(bar_values, bar_labels, primary, 500, 180)
    img.paste(bar_chart, (40, y_pos))

    y_pos += 180

    # ===== 푸터 =====
    footer_y = height - 80
    draw.rectangle([0, footer_y, width, height], fill=primary)
    draw.text((width // 2, footer_y + 25), "쥬팍's Daily Brief", font=fonts["subtitle"], fill="white", anchor="mm")
    draw.text(
        (width // 2, footer_y + 55),
        "© 모든 소유권은 쥬팍에게 있음",
        font=fonts["small"],
        fill=(200, 200, 200),
        anchor="mm",
    )

    # 저장
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG", quality=95)
    return output_path


if __name__ == "__main__":
    print("Generating professional infographic v2...")
    test_summary = [
        "비트코인 10만 달러 돌파, 역사적 신고가 달성",
        "이더리움 업그레이드로 가스비 90% 절감 성공",
        "기관 투자자 유입 가속화, 시장 성숙 신호",
    ]
    test_insight = "암호화폐 시장이 본격적인 성숙기에 진입하며 기관 자금 유입이 가속화되고 있습니다. 이는 장기적 시장 안정성에 긍정적 신호로 해석됩니다."

    output = create_news_card("Crypto", test_summary, test_insight, "output/infographic_v2_test.png")
    print(f"Professional infographic saved: {output}")
