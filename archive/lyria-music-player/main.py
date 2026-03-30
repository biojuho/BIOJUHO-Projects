"""
Lyria Music Player — CLI Entry Point
커맨드라인에서 AI 음악 생성/재생/저장을 제어합니다.

사용법:
    python main.py --prompt "minimal techno" --bpm 90 --duration 30
    python main.py --prompt "lo-fi hip hop" --bpm 80 --no-play --mp3
    python main.py --help
"""

import argparse
import asyncio
import sys

from player import LyriaMusicPlayer


def parse_args() -> argparse.Namespace:
    """CLI 인수를 파싱합니다."""
    parser = argparse.ArgumentParser(
        prog="lyria-player",
        description="🎵 Lyria RealTime Music Player — AI로 음악을 생성하고 재생합니다",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  %(prog)s --prompt "minimal techno" --bpm 90
  %(prog)s --prompt "epic orchestral" --bpm 140 --duration 60
  %(prog)s --prompt "lo-fi hip hop" --no-play --mp3
  %(prog)s --prompt "jazz piano, rainy mood" --output my_jazz.wav
        """,
    )

    parser.add_argument(
        "--prompt",
        "-p",
        type=str,
        default="ambient electronic",
        help="음악 스타일 프롬프트 (기본: 'ambient electronic')",
    )
    parser.add_argument(
        "--weight",
        "-w",
        type=float,
        default=1.0,
        help="프롬프트 가중치 (기본: 1.0)",
    )
    parser.add_argument(
        "--bpm",
        type=int,
        default=120,
        help="BPM 템포 (기본: 120)",
    )
    parser.add_argument(
        "--temperature",
        "-t",
        type=float,
        default=1.0,
        help="생성 다양성 temperature (기본: 1.0, 범위: 0.0~2.0)",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=30,
        help="녹음 시간 (초, 기본: 30)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="출력 WAV 파일명 (기본: lyria_YYYYMMDD_HHMMSS.wav)",
    )
    parser.add_argument(
        "--no-play",
        action="store_true",
        help="스피커 출력 비활성화 (파일 저장만)",
    )
    parser.add_argument(
        "--mp3",
        action="store_true",
        help="WAV → MP3 변환 (ffmpeg 필요)",
    )

    return parser.parse_args()


def main() -> None:
    """CLI 메인 함수."""
    args = parse_args()

    player = LyriaMusicPlayer(
        prompt=args.prompt,
        weight=args.weight,
        bpm=args.bpm,
        temperature=args.temperature,
        duration=args.duration,
        output_filename=args.output,
        enable_playback=not args.no_play,
        convert_mp3=args.mp3,
    )

    try:
        asyncio.run(player.run())
    except KeyboardInterrupt:
        print("\n👋 종료!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
