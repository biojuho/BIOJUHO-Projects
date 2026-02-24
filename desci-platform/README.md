# DSCI-DecentBio

탈중앙화 과학(Decentralized Science) 플랫폼

## Tech Stack
- **Backend:** Python (FastAPI) + Firebase Admin
- **Frontend:** React (Vite) + Tailwind CSS
- **Auth:** Firebase Authentication (Google + Email/PW)

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Quality Gate

### Backend smoke test (pytest)
```bash
cd biolinker
python -m pytest tests/test_smoke_pipeline.py -q
```

### Frontend lint + production build (Node LTS)
```bash
cd frontend
npm run lint
npm run build:lts
npm run check:bundle
```

## Features
- ✅ Google 소셜 로그인
- ✅ Email/Password 인증
- ✅ Firebase Token 검증
- 🔜 연구 논문 업로드
- 🔜 IPFS 탈중앙화 저장
- 🔜 토큰 보상 시스템

## Authors
- Built by Raph & JuPark © 2026
