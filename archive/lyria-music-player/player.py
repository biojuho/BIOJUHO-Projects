"""
Lyria Music Player — Player Engine
Lyria RealTime API에 연결하여 음악을 생성하고 재생/저장합니다.
"""

import asyncio
import signal
import sys

from google import genai
from google.genai import types

from audio_output import AudioPlayer
from audio_writer import AudioWriter
from config import (
    API_VERSION,
    DEFAULT_BPM,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_WEIGHT,
    GOOGLE_API_KEY,
    MAX_RETRIES,
    MODEL_NAME,
    RETRY_BASE_DELAY,
    validate_api_key,
)


class LyriaMusicPlayer:
    """
    Lyria RealTime API를 사용한 AI 음악 플레이어.

    기능:
    - 텍스트 프롬프트로 음악 스타일 지정
    - 실시간 스피커 출력
    - WAV/MP3 파일 저장
    - BPM, temperature 등 설정 변경
    """

    def __init__(
        self,
        prompt: str = DEFAULT_PROMPT,
        weight: float = DEFAULT_WEIGHT,
        bpm: int = DEFAULT_BPM,
        temperature: float = DEFAULT_TEMPERATURE,
        duration: int = 30,
        output_filename: str | None = None,
        enable_playback: bool = True,
        convert_mp3: bool = False,
    ):
        validate_api_key()

        self.prompt = prompt
        self.weight = weight
        self.bpm = bpm
        self.temperature = temperature
        self.duration = duration
        self.output_filename = output_filename
        self.enable_playback = enable_playback
        self.convert_mp3 = convert_mp3

        self._client = genai.Client(
            api_key=GOOGLE_API_KEY,
            http_options={"api_version": API_VERSION},
        )
        self._writer: AudioWriter | None = None
        self._player: AudioPlayer | None = None
        self._stop_event = asyncio.Event()
        self._chunks_received: int = 0

    async def run(self) -> None:
        """메인 실행 루프. 연결 → 설정 → 재생 → 녹음 → 종료."""
        # graceful shutdown 핸들러 등록
        self._setup_signal_handlers()

        print("=" * 50)
        print("🎵 Lyria RealTime Music Player")
        print("=" * 50)
        print(f"  프롬프트 : {self.prompt}")
        print(f"  BPM     : {self.bpm}")
        print(f"  Temp    : {self.temperature}")
        print(f"  녹음시간 : {self.duration}초")
        print(f"  스피커   : {'✅ ON' if self.enable_playback else '❌ OFF'}")
        print(f"  MP3 변환 : {'✅ ON' if self.convert_mp3 else '❌ OFF'}")
        print("=" * 50)
        print()

        # 오디오 출력 초기화
        if self.enable_playback:
            self._player = AudioPlayer()
            if not self._player.available:
                print("ℹ️ 오디오 디바이스 없음 → 파일 저장만 진행")
                self._player = None

        # 재시도 로직으로 연결
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                await self._session_loop()
                break  # 정상 종료
            except Exception as e:
                if attempt < MAX_RETRIES and not self._stop_event.is_set():
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    print(f"⚠️ 연결 오류 (시도 {attempt}/{MAX_RETRIES}): {e}")
                    print(f"   {delay:.0f}초 후 재시도...")
                    await asyncio.sleep(delay)
                else:
                    print(f"❌ 연결 실패: {e}")
                    if self._writer and not self._writer._closed:
                        self._writer.close()
                    raise

    async def _session_loop(self) -> None:
        """Lyria API 세션 연결 및 오디오 수신 루프."""
        print("🔌 Lyria RealTime API 연결 중...")

        async with (
            self._client.aio.live.music.connect(model=MODEL_NAME) as session,
            asyncio.TaskGroup() as tg,
        ):
            print("✅ 연결 성공!")

            # 오디오 Writer 초기화
            self._writer = AudioWriter(filename=self.output_filename)
            self._writer.open()

            # 스피커 출력 시작
            if self._player:
                self._player.start()

            # 백그라운드 수신 태스크
            tg.create_task(self._receive_audio(session))

            # 프롬프트 및 설정 전송
            await session.set_weighted_prompts(
                prompts=[
                    types.WeightedPrompt(text=self.prompt, weight=self.weight),
                ]
            )
            await session.set_music_generation_config(
                config=types.LiveMusicGenerationConfig(
                    bpm=self.bpm,
                    temperature=self.temperature,
                )
            )

            # 재생 시작
            print("▶️ 음악 재생 시작!")
            await session.play()

            # duration 동안 대기 또는 stop 신호 대기
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.duration,
                )
                print("\n⏹️ 사용자에 의해 중지됨")
            except asyncio.TimeoutError:
                print(f"\n⏱️ {self.duration}초 녹음 완료")

            # 세션 종료 전 정지
            await session.pause()

        # 클린업
        self._cleanup()

    async def _receive_audio(self, session) -> None:
        """서버에서 오디오 청크를 수신하고 Writer/Player에 전달합니다."""
        try:
            while not self._stop_event.is_set():
                async for message in session.receive():
                    if self._stop_event.is_set():
                        return

                    # 오디오 청크 추출
                    if (
                        message.server_content
                        and message.server_content.audio_chunks
                    ):
                        for chunk in message.server_content.audio_chunks:
                            audio_data = chunk.data

                            # WAV 저장
                            if self._writer:
                                self._writer.add_chunk(audio_data)

                            # 스피커 출력
                            if self._player:
                                await self._player.feed(audio_data)

                            self._chunks_received += 1

                            # 진행 표시 (10 청크마다)
                            if self._chunks_received % 10 == 0:
                                elapsed = self._writer.duration if self._writer else 0
                                print(
                                    f"\r  🎶 수신 중... {elapsed:.1f}초 녹음됨",
                                    end="",
                                    flush=True,
                                )

                    await asyncio.sleep(1e-12)  # 이벤트 루프 양보

        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not self._stop_event.is_set():
                print(f"\n⚠️ 수신 오류: {e}")
                self._stop_event.set()

    def _cleanup(self) -> None:
        """리소스 정리: 파일 저장 완료, 스피커 정지."""
        print()

        # 스피커 정지
        if self._player:
            self._player.stop()

        # WAV 저장 완료
        if self._writer and not self._writer._closed:
            wav_path = self._writer.close()

            # MP3 변환
            if self.convert_mp3:
                self._writer.to_mp3()

        print()
        print(f"📊 총 수신 청크: {self._chunks_received}")
        print("✅ 완료!")

    def _setup_signal_handlers(self) -> None:
        """Ctrl+C graceful shutdown 핸들러를 등록합니다."""
        def _signal_handler(sig, frame):
            print("\n\n🛑 종료 신호 수신 (Ctrl+C)")
            self._stop_event.set()

        if sys.platform != "win32":
            signal.signal(signal.SIGINT, _signal_handler)
            signal.signal(signal.SIGTERM, _signal_handler)
        else:
            signal.signal(signal.SIGINT, _signal_handler)
