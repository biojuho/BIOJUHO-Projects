# DSCI-DecentBio

탈중앙화 과학(Decentralized Science) 플랫폼
Decentralized Science (DeSci) Platform
## Target Audience

**Dual Persona Platform**: B2B Prosumer (Researchers + VCs)

**Persona A**: "Research Funding Seeker" (박민지, 35세 박사후연구원)
- PhD-level researchers at universities, institutes, or bio-startups
- Pain point: Difficulty securing research funding, lack of VC network
- Need: Auto-discovery of matching RFPs, AI-generated proposal drafts
- Decision criteria: Matching accuracy >80%, time savings (3 days → 1 day)

**Persona B**: "Bio Investment Scout" (김태준, 42세 VC 파트너)
- VC partners/analysts managing bio funds
- Pain point: Difficulty finding quality research, insufficient time for tech evaluation
- Need: Early discovery of high-value projects, automated tech assessment
- Decision criteria: Clear ROI, risk assessment, matching algorithm trustworthiness

**What They Need**:
- RFP crawling + vector search for accurate matching
- AI proposal generator (save 100+ hours of funding search)
- VC dashboard for investment opportunity visualization
- IPFS permanent data storage (core DeSci value)
- DAO governance for transparent decision-making

**Success Metrics**:
- Matching relevance satisfaction >80%
- Proposal submission rate >60% (after matching)
- VC project evaluation rate >40% (of recommendations)
- Successful matches: >5/month (funding secured or investment closed)

For detailed audience analysis, see [workspace-audience-profiles.md](../../../.claude/skills/audience-first/references/workspace-audience-profiles.md#3-desci-platform-biolinker).



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

### UTF-8 테스트 실행 (Windows)

Windows 터미널에서 한글이 깨져 보여도 파일 자체가 손상된 것은 아닐 수 있습니다. 로컬 테스트는 UTF-8 강제 실행을 기본으로 사용하세요.

```bash
set PYTHONUTF8=1
cd ..\tests
..\.venv\Scripts\python.exe -m pytest test_shared_llm.py -q
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
