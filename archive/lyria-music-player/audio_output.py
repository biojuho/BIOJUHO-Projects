"""
Lyria Music Player — Audio Output
sounddevice를 사용하여 PCM 오디오를 실시간으로 스피커에 출력
"""

import asyncio
import threading

import numpy as np
import sounddevice as sd
from config import CHANNELS, DTYPE, SAMPLE_RATE


class AudioPlayer:
    """
    비동기 큐 기반 실시간 오디오 재생기.
    Lyria API에서 수신한 PCM 청크를 스피커로 출력합니다.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS):
        self.sample_rate = sample_rate
        self.channels = channels
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=50)
        self._stream: sd.OutputStream | None = None
        self._thread: threading.Thread | None = None
        self._running: bool = False
        self._available: bool = True

        # 오디오 디바이스 확인
        try:
            sd.check_output_settings(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=DTYPE,
            )
        except sd.PortAudioError:
            self._available = False
            print("⚠️ 오디오 출력 디바이스를 찾을 수 없습니다.")
            print("   파일 저장만 진행합니다.")

    @property
    def available(self) -> bool:
        """오디오 출력 디바이스가 사용 가능한지 반환합니다."""
        return self._available

    async def feed(self, data: bytes) -> None:
        """오디오 청크를 재생 큐에 추가합니다."""
        if not self._available or not self._running:
            return
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            # 큐가 가득 차면 가장 오래된 데이터를 버림 (실시간 재생 우선)
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self._queue.put_nowait(data)

    def start(self) -> None:
        """오디오 스트림을 시작합니다."""
        if not self._available:
            return

        self._running = True
        self._stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=DTYPE,
            blocksize=4096,
        )
        self._stream.start()
        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()
        print("🔊 스피커 출력 시작")

    def _playback_loop(self) -> None:
        """백그라운드 스레드에서 큐의 오디오를 재생합니다."""
        loop = asyncio.new_event_loop()
        while self._running:
            try:
                # 블로킹 방식으로 큐에서 데이터 가져오기
                data = loop.run_until_complete(asyncio.wait_for(self._queue.get(), timeout=0.5))
                if data is None:  # 종료 신호
                    break

                # bytes → numpy int16 배열 → 스테레오 reshape
                samples = np.frombuffer(data, dtype=np.int16)
                if self.channels > 1:
                    # 스테레오: interleaved → (frames, channels)
                    samples = samples.reshape(-1, self.channels)

                if self._stream is not None and self._stream.active:
                    self._stream.write(samples)

            except TimeoutError:
                continue
            except Exception as e:
                if self._running:
                    print(f"⚠️ 재생 오류: {e}")
                break
        loop.close()

    def stop(self) -> None:
        """오디오 스트림을 정지합니다."""
        self._running = False

        # 종료 신호 전송
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        print("🔇 스피커 출력 정지")
