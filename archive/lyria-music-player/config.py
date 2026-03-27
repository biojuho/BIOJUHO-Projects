"""
Lyria Music Player — Configuration
환경변수 로드 및 기본 설정 관리
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# ── API 설정 ──────────────────────────────────────────────
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
API_VERSION: str = "v1alpha"
MODEL_NAME: str = "models/lyria-realtime-exp"

# ── 오디오 상수 (Lyria RealTime 출력 포맷) ─────────────────
SAMPLE_RATE: int = 48_000       # 48 kHz
CHANNELS: int = 2               # 스테레오
SAMPLE_WIDTH: int = 2           # 16-bit (2 bytes per sample)
DTYPE: str = "int16"            # numpy dtype

# ── 음악 생성 기본값 ──────────────────────────────────────
DEFAULT_PROMPT: str = "ambient electronic"
DEFAULT_WEIGHT: float = 1.0
DEFAULT_BPM: int = 120
DEFAULT_TEMPERATURE: float = 1.0
DEFAULT_DURATION: int = 30      # 초

# ── 출력 경로 ─────────────────────────────────────────────
OUTPUT_DIR: Path = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── 재연결 설정 ───────────────────────────────────────────
MAX_RETRIES: int = 3
RETRY_BASE_DELAY: float = 1.0   # 초 (exponential backoff)


def validate_api_key() -> None:
    """API 키 유효성 검사. 미설정 시 명확한 메시지 출력 후 종료."""
    if not GOOGLE_API_KEY:
        print("=" * 60)
        print("❌ GOOGLE_API_KEY가 설정되지 않았습니다!")
        print()
        print("  1. https://aistudio.google.com/apikey 에서 API 키 발급")
        print("  2. .env 파일 생성:")
        print("     GOOGLE_API_KEY=your_api_key_here")
        print()
        print("  또는 환경변수로 직접 설정:")
        print("     set GOOGLE_API_KEY=your_api_key_here  (Windows)")
        print("     export GOOGLE_API_KEY=your_api_key_here (Linux/Mac)")
        print("=" * 60)
        sys.exit(1)
