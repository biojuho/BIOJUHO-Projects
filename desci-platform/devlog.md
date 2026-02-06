# Devlog: Desci Platform (BioLinker)

## 2026-02-06 (플랫폼 확장)

### 1. 핵심 기능 구현 (MVP)
- **인증 시스템**: Firebase Auth 연동 (Google 로그인, 이메일 가입).
- **BioLinker 엔진**: `analyzer.py`를 통해 RFP 공고문과 기업 프로필의 적합도를 분석하는 AI 로직 구현.
- **크롤러 모듈**: KDDF, NTIS 공고 수집을 위한 기본 구조 (`models.py`, `crawler.py`) 설계.

### 2. 플랫폼 기능 확장 (DeSci Features)
- **연구 논문 업로드 (`/upload`)**:
  - IPFS(Pinata) 연동을 위한 백엔드/프론트엔드 구현.
  - PDF 업로드 시 `Paper` 데이터 모델 생성 및 보상 트리거.
- **토큰 경제 시스템 (`/wallet`)**:
  - Web3 기반 `DeSciToken` 보상 로직 설계 (Mock 모드 지원).
  - 지갑 페이지에서 잔액 및 보상 내역 조회 기능 추가.
- **내 연구실 (`/mylab`)**:
  - 연구자 대시보드 `MyLab.jsx` 신규 개발.
  - 내 연구 목록 및 심사 상태(보상 여부) 확인 기능 구현.

### 3. 기술 스택
- **Backend**: FastAPI, Web3.py, Aiohttp, LangChain
- **Frontend**: React (Vite), TailwindCSS, Firebase SDK
- **Blockchain**: Ethereum Sepolia (Prepared for Deployment), IPFS (Pinata)
