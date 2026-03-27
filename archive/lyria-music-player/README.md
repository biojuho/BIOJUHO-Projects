# 🎵 Lyria RealTime Music Player

Google DeepMind의 **Lyria RealTime API**를 사용한 AI 음악 생성기.
텍스트 프롬프트로 음악 스타일을 지정하면, AI가 실시간으로 음악을 생성하고 재생합니다.

## ✨ Features

- 🎶 **실시간 AI 음악 생성** — 텍스트로 장르/분위기 지정
- 🔊 **스피커 실시간 출력** — 생성과 동시에 음악을 들을 수 있음
- 💾 **WAV 파일 저장** — 48kHz 스테레오 고품질 녹음
- 🎵 **MP3 변환** — ffmpeg로 자동 변환
- ⚡ **CLI 인터페이스** — 간단한 커맨드로 제어

## 📋 Prerequisites

- Python 3.11+
- Google AI API Key ([발급](https://aistudio.google.com/apikey))
- (선택) ffmpeg — MP3 변환용

## 🚀 Quick Start

### 1. 설치

```bash
cd lyria-music-player
pip install -r requirements.txt
```

### 2. API 키 설정

```bash
# .env 파일 생성
cp .env.example .env
# .env 파일을 열어 GOOGLE_API_KEY 값을 입력
```

### 3. 실행

```bash
# 기본 실행 (ambient electronic, 30초)
python main.py

# 미니멀 테크노, BPM 90, 1분
python main.py --prompt "minimal techno" --bpm 90 --duration 60

# 로파이 힙합, 스피커 출력 없이 파일만 저장 + MP3 변환
python main.py --prompt "lo-fi hip hop" --bpm 80 --no-play --mp3

# 도움말
python main.py --help
```

## 🎛️ CLI Options

| 옵션 | 단축 | 기본값 | 설명 |
|------|------|--------|------|
| `--prompt` | `-p` | `ambient electronic` | 음악 스타일 프롬프트 |
| `--weight` | `-w` | `1.0` | 프롬프트 가중치 |
| `--bpm` | | `120` | BPM 템포 |
| `--temperature` | `-t` | `1.0` | 생성 다양성 (0.0~2.0) |
| `--duration` | `-d` | `30` | 녹음 시간 (초) |
| `--output` | `-o` | 자동 생성 | 출력 WAV 파일명 |
| `--no-play` | | | 스피커 출력 비활성화 |
| `--mp3` | | | MP3 변환 (ffmpeg 필요) |

## 📂 Project Structure

```
lyria-music-player/
├── main.py           # CLI 진입점
├── player.py         # 플레이어 엔진 (API 연결 + 재생)
├── audio_writer.py   # WAV/MP3 파일 저장
├── audio_output.py   # 실시간 스피커 출력
├── config.py         # 설정 관리
├── requirements.txt  # 의존성
├── .env.example      # API 키 템플릿
└── output/           # 생성된 음악 파일 (자동 생성)
```

## 🎵 Prompt Examples

| 프롬프트 | BPM | 설명 |
|---------|-----|------|
| `minimal techno` | 125 | 미니멀 테크노 |
| `lo-fi hip hop, rainy day` | 80 | 비 오는 날 로파이 |
| `epic orchestral` | 140 | 웅장한 오케스트라 |
| `jazz piano, smooth` | 95 | 부드러운 재즈 피아노 |
| `ambient electronic, space` | 70 | 우주 느낌 앰비언트 |
| `drum and bass, energetic` | 170 | 에너지틱한 드럼앤베이스 |

## ⚡ Tips

- **Ctrl+C**로 언제든 중지 가능 (WAV 파일은 자동 저장됨)
- `temperature`를 높이면 더 다양한 음악이 생성됨
- 여러 스타일을 쉼표로 조합 가능: `"jazz, electronic, calm"`
- 오디오 디바이스가 없으면 자동으로 파일 저장만 진행

## 📄 License

MIT
