# DeSci Platform Deployment Guide

이 문서는 DeSci 플랫폼(Frontend + Backend + Smart Contracts)을 프로덕션 클라우드 환경과 블록체인 네트워크에 배포하기 위한 최종 가이드입니다.

## 1. Smart Contract 배포 (Polygon Amoy Testnet)

DeSci 플랫폼의 핵심 토큰인 `DSCIToken`과 연구 자산 영구 보존용 `BioLinker (IP-NFT)` 컨트랙트를 Polygon Amoy 테스트넷에 배포합니다.

### 사전 준비
1. `contracts/.env` 파일을 생성합니다 (`.env.example` 복사).
2. Metamask 등 지갑에서 추출한 `PRIVATE_KEY`를 넣습니다.
3. [Polygon Faucet](https://faucet.polygon.technology/)에서 Amoy 테스트넷 MATIC을 발급받습니다.

### 배포 실행
```bash
cd contracts
npm install
npm run deploy:amoy
```

배포가 완료되면 콘솔에 출력되는 **DSCIToken**과 **BioLinker** 주소를 프론트엔드 환경 변수나 백엔드 설정에 업데이트합니다.

---

## 2. Backend 배포 (Railway)

백엔드 파이썬 서버(FastAPI + Vector DB)는 인프라 관리가 쉬운 Railway를 통해 배포합니다.

### 사전 준비
- Railway 계정 및 CLI 설치 (`npm i -g @railway/cli`)
- [Stripe Dashboard](https://dashboard.stripe.com/)에서 Webhook Secret 및 Price ID 발급 (선택)

### 배포 실행
```bash
railway login
railway link  # DeSci 플랫폼 프로젝트 선택 또는 신규 생성
railway up
```

### 필수 환경 변수 (Railway Dashboard에서 설정)
- `DATABASE_URL` (Railway에서 제공하는 PostgreSQL 또는 Redis 플러그인 연결)
- `STRIPE_SECRET_KEY` (선택, 없을 시 모의 결제 동작)
- `VITE_API_BASE_URL` (프론트엔드가 참조할 실제 Railway URL)

---

## 3. Frontend 배포 (Vercel)

프론트엔드 리액트(Vite) 앱은 Vercel을 통해 엣지 네트워크에 빠르고 안정적으로 배포됩니다.

### 사전 준비
- Vercel 계정 및 CLI 설치 (`npm i -g vercel`)

### 배포 실행
```bash
cd frontend
vercel login
vercel --prod
```

### 필수 환경 변수 (Vercel Dashboard에서 설정)
- `VITE_API_BASE_URL` : Railway에 배포된 백엔드 URL (예: `https://desci-api.up.railway.app`)

---

## 4. 최종 확인
1. Vercel 도메인에 접속하여 랜딩 페이지가 정상 표시되는지 확인.
2. `/explore` 접속 시 백엔드(Railway)와 통신하여 논문 피드를 잘 가져오는지 확인.
3. `/vc` 대시보드에 50개 VC 리스트가 정상적으로 표시되는지 확인.
4. (테스트) 로그인 후 지갑 연동 및 Polygon Amoy 네트워크 전환 정상 여부 확인.
