"""Reels auto-creation pipeline.

Generates Instagram Reels from text topics:
  Topic → Script → TTS → SRT subtitles → Background video → FFmpeg assembly

Inspired by Reelsfy + short-video-maker patterns.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.llm import TaskTier, get_client

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REELS_DIR = DATA_DIR / "reels"
REELS_DIR.mkdir(parents=True, exist_ok=True)


# ---- Prompt templates ----

SCRIPT_PROMPT = """\
당신은 인스타그램 릴스 대본 작가입니다.
다음 주제로 30~60초 릴스 대본을 작성하세요.

## 주제
{topic}

## 구조
1. **HOOK** (0~5초): 강력한 첫마디로 시청 유지
2. **BODY** (5~45초): 핵심 정보 3가지 전달
3. **CTA** (45~60초): 팔로우/저장/댓글 유도

## 규칙
- 구어체 한국어 (읽었을 때 자연스럽게)
- 각 구간 사이 [PAUSE] 표시
- 전체 200~400자 내외
- 이모지 사용 금지 (음성용)

## 출력 (JSON)
{{
  "hook": "첫마디 텍스트",
  "body": ["포인트 1", "포인트 2", "포인트 3"],
  "cta": "마무리 텍스트",
  "full_script": "전체 대본 (음성용)",
  "estimated_duration": 45
}}"""


@dataclass
class ReelsScript:
    """Structured reels script."""

    hook: str = ""
    body: list[str] = field(default_factory=list)
    cta: str = ""
    full_script: str = ""
    estimated_duration: int = 45

    @classmethod
    def from_dict(cls, data: dict) -> ReelsScript:
        return cls(
            hook=data.get("hook", ""),
            body=data.get("body", []),
            cta=data.get("cta", ""),
            full_script=data.get("full_script", ""),
            estimated_duration=data.get("estimated_duration", 45),
        )


@dataclass
class SRTEntry:
    """A single SRT subtitle entry."""

    index: int
    start_time: str  # HH:MM:SS,mmm
    end_time: str
    text: str

    def to_srt(self) -> str:
        return f"{self.index}\n{self.start_time} --> {self.end_time}\n{self.text}\n"


@dataclass
class ReelResult:
    """Result from reel creation."""

    script: ReelsScript
    audio_path: str = ""
    srt_path: str = ""
    video_path: str = ""
    success: bool = False
    error: str = ""


class ReelsGenerator:
    """Generate Instagram Reels from text topics."""

    def __init__(self):
        self._llm = get_client()

    async def generate_script(self, topic: str) -> ReelsScript:
        """Generate a structured reels script for the topic."""
        prompt = SCRIPT_PROMPT.format(topic=topic)
        resp = await self._llm.acreate(
            tier=TaskTier.STANDARD,
            messages=[{"role": "user", "content": prompt}],
            system="Reels script writer. Output JSON only.",
        )
        try:
            data = json.loads(resp.text.strip())
            script = ReelsScript.from_dict(data)
            logger.info(
                "Script generated: %d chars, ~%ds",
                len(script.full_script),
                script.estimated_duration,
            )
            return script
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Script parse failed: %s — using raw text", e)
            return ReelsScript(
                full_script=resp.text.strip(),
                estimated_duration=45,
            )

    def generate_tts(
        self,
        text: str,
        output_path: str | Path | None = None,
        lang: str = "ko",
    ) -> Path:
        """Generate TTS audio from text using gTTS.

        Returns path to the generated MP3 file.
        """
        try:
            from gtts import gTTS
        except ImportError:
            logger.error("gTTS not installed — run: pip install gTTS")
            raise

        if output_path is None:
            import time

            output_path = REELS_DIR / f"tts_{int(time.time())}.mp3"
        output_path = Path(output_path)

        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(str(output_path))
        logger.info("TTS saved: %s (%.1f KB)", output_path.name, output_path.stat().st_size / 1024)
        return output_path

    def generate_srt(
        self,
        script: ReelsScript,
        output_path: str | Path | None = None,
    ) -> Path:
        """Generate SRT subtitle file from script structure.

        Splits script into timed segments based on structure.
        """
        if output_path is None:
            import time

            output_path = REELS_DIR / f"subs_{int(time.time())}.srt"
        output_path = Path(output_path)

        entries: list[SRTEntry] = []
        idx = 1
        current_sec = 0.0

        # Hook: 0~5s
        if script.hook:
            entries.append(
                SRTEntry(
                    index=idx,
                    start_time=self._format_time(current_sec),
                    end_time=self._format_time(5.0),
                    text=script.hook,
                )
            )
            idx += 1
            current_sec = 5.0

        # Body: distribute evenly between 5s and (duration - 10s)
        body_end = max(script.estimated_duration - 10, 20)
        if script.body:
            segment_dur = (body_end - current_sec) / len(script.body)
            for point in script.body:
                end = current_sec + segment_dur
                entries.append(
                    SRTEntry(
                        index=idx,
                        start_time=self._format_time(current_sec),
                        end_time=self._format_time(end),
                        text=point,
                    )
                )
                idx += 1
                current_sec = end

        # CTA: last 10s
        if script.cta:
            entries.append(
                SRTEntry(
                    index=idx,
                    start_time=self._format_time(current_sec),
                    end_time=self._format_time(float(script.estimated_duration)),
                    text=script.cta,
                )
            )

        srt_content = "\n".join(e.to_srt() for e in entries)
        output_path.write_text(srt_content, encoding="utf-8")
        logger.info("SRT saved: %s (%d entries)", output_path.name, len(entries))
        return output_path

    def assemble_video(
        self,
        audio_path: Path,
        srt_path: Path,
        output_path: Path | None = None,
        duration: int = 45,
    ) -> Path | None:
        """Assemble reel video with audio + subtitles using FFmpeg.

        Creates a simple color background with burned-in subtitles.
        Returns output path or None if FFmpeg is unavailable.
        """
        if output_path is None:
            import time

            output_path = REELS_DIR / f"reel_{int(time.time())}.mp4"

        # Check FFmpeg availability
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            logger.warning("FFmpeg not found — video assembly skipped")
            return None

        # Generate background color video + overlay audio + burn subtitles
        cmd = [
            "ffmpeg",
            "-y",
            # Dark gradient background (1080x1920 vertical)
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x1a1a2e:s=1080x1920:d={duration}:r=30",
            # Audio
            "-i",
            str(audio_path),
            # Subtitle overlay
            "-vf",
            f"subtitles={srt_path}:force_style='FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Alignment=2,MarginV=120'",
            # Output settings
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(output_path),
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=120)
            logger.info("Reel video saved: %s", output_path.name)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error("FFmpeg failed: %s", e.stderr[:500] if e.stderr else str(e))
            return None
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out (120s)")
            return None

    async def create_reel(self, topic: str) -> ReelResult:
        """Full pipeline: topic → script → TTS → SRT → video.

        Returns ReelResult with paths to all generated assets.
        """
        try:
            # 1. Generate script
            script = await self.generate_script(topic)

            if not script.full_script:
                return ReelResult(script=script, error="Empty script generated")

            # 2. Generate TTS audio
            audio_path = self.generate_tts(script.full_script)

            # 3. Generate SRT subtitles
            srt_path = self.generate_srt(script)

            # 4. Assemble video (optional — depends on FFmpeg)
            video_path = self.assemble_video(audio_path, srt_path, duration=script.estimated_duration)

            return ReelResult(
                script=script,
                audio_path=str(audio_path),
                srt_path=str(srt_path),
                video_path=str(video_path) if video_path else "",
                success=True,
            )
        except Exception as e:
            logger.error("Reel creation failed: %s", e)
            return ReelResult(
                script=ReelsScript(),
                error=str(e),
            )

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Convert seconds to SRT time format HH:MM:SS,mmm."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
