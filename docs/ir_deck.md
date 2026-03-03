# AgriGuard × DeSci Platform — Investor Relations Deck

---

## 1. 비전 (Vision)

> "블록체인으로 신뢰할 수 있는 식품 공급망과 탈중앙화 과학 연구 생태계를 구축합니다."

**AgriGuard**: 농산물 공급망의 투명성을 블록체인으로 보장
**DeSci Platform**: 연구 논문의 IP를 NFT로 보호하고 DSCI 토큰으로 인센티브 제공

---

## 2. 문제 (Problem)

| 영역 | 문제 | 규모 |
|---|---|---|
| 식품 안전 | 위변조·리콜 추적 불가 | 연간 $44B 손실 (WHO) |
| 콜드체인 | 온도 이탈 사고 감지 지연 | 의약품 20% 운송 중 손상 |
| 연구 생태계 | 연구자 기여 인정 미흡 | 피어리뷰 보상 $0 |
| IP 보호 | 논문 저작권 분쟁 증가 | 연간 7% 증가 |

---

## 3. 솔루션 (Solution)

### AgriGuard
- QR 코드 → 블록체인 이력 추적 (파종→수확→운송→판매)
- IoT 센서 → 실시간 콜드체인 모니터링 (온도/습도 5초 단위)
- 이상 감지 → 자동 알림 + 블록체인 기록

### DeSci Platform (BioLinker)
- 논문 업로드 → IPFS 저장 → IP-NFT 민팅
- DSCI 토큰 보상: 업로드(100), 피어리뷰(50), 데이터 공유(200)
- DAO 거버넌스: 토큰 기반 의사결정

---

## 4. 기술 아키텍처

```
┌─ Frontend (React + Vite + TailwindCSS) ─────┐
│  AgriGuard UI        DeSci Platform UI       │
│  ColdChainMonitor    Governance / UploadPaper │
└──────────────── HTTPS (Nginx) ───────────────┘
         │                      │
┌─ Backend ─────────────────────────────────────┐
│  FastAPI + SQLAlchemy    FastAPI + ChromaDB    │
│  IoT WebSocket           IPFS + Pinata        │
└──────────────────────────────────────────────┘
         │                      │
┌─ Blockchain (Ethereum / Sepolia) ─────────────┐
│  AgriGuard.sol    DSCIToken.sol  BioLinker.sol │
│                   DeSciDAO.sol                 │
└──────────────────────────────────────────────┘
```

---

## 5. 시장 규모 (Market)

| 시장 | 2025 규모 | 2030 CAGR |
|---|---|---|
| 블록체인 공급망 | $3.4B | 48.3% |
| DeSci/IP-NFT | $0.5B | 65% |
| 농업 IoT | $14.7B | 9.4% |
| **Total SAM** | **$18.6B** | |

---

## 6. 비즈니스 모델

| 수익원 | 구조 |
|---|---|
| SaaS 구독 | 농장/기업별 월 구독 (대시보드 + IoT) |
| 트랜잭션 수수료 | NFT 민팅 · DAO 투표 수수료 (1-2%) |
| 프리미엄 API | 콜드체인 분석 리포트 · 적합도 매칭 |
| 토큰 이코노미 | DSCI 토큰 유통 수수료 |

---

## 7. 제품 현황 (Traction)

| 지표 | 현재 |
|---|---|
| 스마트 컨트랙트 | 4개 배포 준비 완료 (Sepolia) |
| 프론트엔드 | AgriGuard 6페이지 + DeSci 12페이지 |
| 백엔드 API | AgriGuard 15+ / DeSci 20+ 엔드포인트 |
| CI/CD | GitHub Actions 자동화 |
| 테스트 | Unit + Integration + E2E (Playwright) |
| i18n | 한국어/영어 다국어 |

---

## 8. 팀 구성

| 역할 | 이름 | 강점 |
|---|---|---|
| PM/기획 | 아라 | 프로젝트 전략, AI 파이프라인 |
| QA | 지은 | 테스트 자동화, E2E |
| Frontend | 준호 | React, Framer Motion, Web3 |
| Backend | 민석 | FastAPI, Smart Contract, IPFS |
| UX/UI | 하린 | Glassmorphism, a11y |
| DevOps | 현우 | Docker, CI/CD, HTTPS |
| Legal | 수현 | IP 해싱, 규제 준수 |

---

## 9. 로드맵

| 시기 | 마일스톤 |
|---|---|
| 2026 Q1 ✅ | MVP 완성, Sepolia 배포, CI/CD |
| 2026 Q2 | Mainnet 배포, 파일럿 파트너십 3곳 |
| 2026 Q3 | IoT 하드웨어 연동, 500 유저 |
| 2026 Q4 | 토큰 세일, 글로벌 확장 |

---

## 10. 투자 요청 (Ask)

| 항목 | 금액 | 용도 |
|---|---|---|
| Seed Round | $500K | 개발(60%), 인프라(20%), 마케팅(20%) |
| 기대 ROI | 12개월 내 10x | 토큰 이코노미 + SaaS 수익 |
