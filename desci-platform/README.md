# DSCI-DecentBio

탈중앙화 과학(Decentralized Science) 플랫폼  
Decentralized Science (DeSci) Platform

## 🛠 기술 스택 (Tech Stack)

- **Backend:** Python (FastAPI) + Firebase Admin
- **Frontend:** React (Vite) + Tailwind CSS
- **Auth(인증):** Firebase Authentication (Google + Email/PW)

---

## 🚀 빠른 시작 (Quick Start)

### 백엔드 (Backend)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### 프론트엔드 (Frontend)

```bash
cd frontend
npm install
npm run dev
```

---

## 🛡 품질 게이트 (Quality Gate)

작업 공간 통합 정책 및 CI 게이트 (Workspace-wide policy and CI gate): [../QUALITY_GATE.md](../QUALITY_GATE.md)

### 백엔드 스모크 테스트 (Backend smoke test - pytest)

```bash
cd biolinker
python -m pytest tests/test_smoke_pipeline.py -q
```

### 프론트엔드 린트 + 프로덕션 빌드 (Frontend lint + production build - Node LTS)

```bash
cd frontend
npm run lint
npm run build:lts
npm run check:bundle
```

---

## ✨ 주요 기능 (Features)

- ✅ Google 소셜 로그인 (Google Social Login)
- ✅ Email/Password 인증 (Email/Password Authentication)
- ✅ Firebase Token 검증 (Firebase Token Verification)
- ✅ 연구 논문 업로드 (Research Paper Upload)
- ✅ IPFS 탈중앙화 저장 (IPFS Decentralized Storage)
- ✅ 토큰 보상 시스템 (Token Reward System)
- ✅ Peer Review 시스템 (Peer Review & DSCI Rewards)
- ✅ IP-NFT 민팅 (Research Paper NFT Minting)
- ✅ Framer Motion 마이크로 인터랙션

---

## 👨‍💻 작성자 (Authors)

- Built by Raph & JuPark © 2026
