"""
Lyria Music Player — Audio Writer
PCM 오디오 데이터를 WAV 파일로 저장하고, 선택적으로 MP3로 변환
"""

import subprocess
import wave
from datetime import datetime
from pathlib import Path

from config import CHANNELS, OUTPUT_DIR, SAMPLE_RATE, SAMPLE_WIDTH


class AudioWriter:
    """수신한 PCM 오디오 청크를 WAV 파일로 저장합니다."""

    def __init__(self, filename: str | None = None, output_dir: Path = OUTPUT_DIR):
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"lyria_{timestamp}.wav"

        self.wav_path = output_dir / filename
        output_dir.mkdir(parents=True, exist_ok=True)

        self._wav_file: wave.Wave_write | None = None
        self._total_frames: int = 0
        self._closed: bool = False

    def open(self) -> "AudioWriter":
        """WAV 파일을 열고 헤더를 설정합니다."""
        self._wav_file = wave.open(str(self.wav_path), "wb")
        self._wav_file.setnchannels(CHANNELS)
        self._wav_file.setsampwidth(SAMPLE_WIDTH)
        self._wav_file.setframerate(SAMPLE_RATE)
        return self

    def add_chunk(self, data: bytes) -> None:
        """PCM 오디오 청크를 WAV 파일에 추가합니다."""
        if self._wav_file is None:
            raise RuntimeError("AudioWriter가 열리지 않았습니다. open()을 먼저 호출하세요.")
        if self._closed:
            return

        self._wav_file.writeframes(data)
        # 프레임 수 계산: bytes / (channels * sample_width)
        frame_count = len(data) // (CHANNELS * SAMPLE_WIDTH)
        self._total_frames += frame_count

    def close(self) -> Path:
        """WAV 파일을 닫고 저장을 완료합니다. 저장된 파일 경로를 반환합니다."""
        if self._wav_file is not None and not self._closed:
            self._wav_file.close()
            self._closed = True

        duration = self._total_frames / SAMPLE_RATE if SAMPLE_RATE > 0 else 0
        print(f"💾 WAV 저장 완료: {self.wav_path}")
        print(f"   길이: {duration:.1f}초 | 크기: {self.wav_path.stat().st_size / 1024 / 1024:.1f}MB")

        return self.wav_path

    def to_mp3(self) -> Path | None:
        """
        저장된 WAV 파일을 MP3로 변환합니다.
        ffmpeg가 필요합니다. 없으면 경고만 출력하고 None을 반환합니다.
        """
        if not self._closed:
            self.close()

        mp3_path = self.wav_path.with_suffix(".mp3")

        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(self.wav_path),
                    "-codec:a", "libmp3lame",
                    "-qscale:a", "2",       # 고품질 VBR
                    str(mp3_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                mp3_size = mp3_path.stat().st_size / 1024 / 1024
                print(f"🎵 MP3 변환 완료: {mp3_path} ({mp3_size:.1f}MB)")
                return mp3_path
            else:
                print(f"⚠️ MP3 변환 실패: {result.stderr[:200]}")
                return None
        except FileNotFoundError:
            print("⚠️ ffmpeg가 설치되어 있지 않습니다. MP3 변환을 건너뜁니다.")
            print("   설치: https://ffmpeg.org/download.html")
            return None
        except subprocess.TimeoutExpired:
            print("⚠️ MP3 변환 시간 초과 (120초)")
            return None

    def __enter__(self) -> "AudioWriter":
        return self.open()

    def __exit__(self, *args) -> None:
        if not self._closed:
            self.close()

    @property
    def duration(self) -> float:
        """현재까지 녹음된 시간(초)을 반환합니다."""
        return self._total_frames / SAMPLE_RATE if SAMPLE_RATE > 0 else 0.0
