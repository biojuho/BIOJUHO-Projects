# GitHub Adoption Roadmap for desci-platform

Updated: 2026-03-20

## 1. 목적

이 문서는 `desci-platform` 개선을 위해 GitHub 오픈소스를 어떤 순서로 도입할지 정리한 실행용 로드맵이다.
목표는 "좋아 보이는 프로젝트 수집"이 아니라, 현재 코드베이스의 약점을 가장 적은 리스크로 보강하는 것이다.

핵심 기준은 아래 4가지다.

1. 현재 아키텍처와 바로 연결될 것
2. 운영 복잡도 대비 개선 효과가 클 것
3. PoC 후 롤백이 쉬울 것
4. 제품 신뢰도와 사용자 경험을 동시에 올릴 것

## 2. 현재 상태 요약

현재 코드베이스에서 확인한 핵심 제약은 아래와 같다.

- 논문 PDF 처리는 `pypdf` 기반 단순 텍스트 추출 위주다.
- 논문/자산 인덱싱은 구조화 메타데이터보다 평문 중심이다.
- 검색은 로컬 `ChromaDB`와 fallback 로직에 의존한다.
- 지갑 연결은 `window.ethereum` 직접 호출 수준이다.
- 거버넌스는 Firestore 문서와 고정 투표 가중치 기반 MVP다.
- 크롤링과 인덱싱 운영은 `APScheduler + JSON` 저장 구조라 장애 대응과 관찰성이 약하다.

이 때문에 우선순위는 아래 축에 맞춰야 한다.

- 논문 구조화
- 검색 품질 및 필터링
- 지갑/신원 UX
- 데이터 파이프라인 운영 안정화
- DAO 신뢰도 보강

## 3. 권장 도입 후보

| 우선순위 | 프로젝트 | 권장 용도 | 도입 판단 |
| --- | --- | --- | --- |
| P0 | `grobidOrg/grobid` | 논문 PDF 구조화 파싱 | 바로 도입 |
| P0 | `wevm/wagmi` + `rainbow-me/rainbowkit` + `spruceid/siwe` | 지갑 연결, 서명 로그인, 프론트 UX 개선 | 바로 도입 |
| P1 | `qdrant/qdrant` | 벡터 검색, payload filter, hybrid search | 단계 도입 |
| P1 | `PrefectHQ/prefect` | 수집/인덱싱 워크플로 운영화 | 단계 도입 |
| P2 | `snapshot-labs/snapshot-*` | 오프체인 가스리스 거버넌스 | 기능 확장 시 도입 |
| P3 | `IQSS/dataverse` | 연구 데이터 저장소, DOI/보존/리뷰 워크플로 | 전략 과제로 보류 |

## 4. 프로젝트별 도입안

### 4.1 GROBID

- GitHub: <https://github.com/grobidOrg/grobid>
- 도입 목적:
  논문 업로드 시 제목, 초록, 저자, 소속, 참고문헌, 섹션 구조를 추출해 현재의 단순 텍스트 인덱싱을 개선한다.
- 현재 연결 지점:
  `biolinker/services/pdf_parser.py`
  `biolinker/services/asset_manager.py`
  `biolinker/services/vector_store.py`
- 기대 효과:
  검색 정확도 상승, RFP 매칭 품질 개선, 논문 메타데이터 신뢰도 향상, 향후 DOI/ORCID 연동 기반 확보
- 도입 방식:
  `pdf_parser.py`를 즉시 교체하지 말고 `GROBIDParser`를 추가한다.
  실패 시 기존 `pypdf` 파서로 fallback 하도록 구성한다.
- 리스크:
  Java 기반 서비스라 메모리 사용량이 증가한다.
- 판단:
  가장 먼저 붙여도 되는 고효율 개선안

### 4.2 wagmi + RainbowKit + SIWE

- GitHub:
  <https://github.com/wevm/wagmi>
  <https://github.com/rainbow-me/rainbowkit>
  <https://github.com/spruceid/siwe>
- 도입 목적:
  월렛 연결, 체인 상태 관리, 서명 로그인, 연결 UI를 표준화한다.
- 현재 연결 지점:
  `frontend/src/contexts/AuthContext.jsx`
  `/wallet`, `/nft/mint`, `/reward/*`
- 기대 효과:
  MetaMask/Rabby 외 확장성 확보, 연결 실패율 감소, 사용자 신뢰도 향상, wallet identity 기반 기능 확장
- 도입 방식:
  Firebase 로그인은 유지한다.
  `walletAddress` 상태 관리만 먼저 `wagmi`로 교체한다.
  이후 `SIWE` nonce/verify endpoint를 백엔드에 추가해 wallet sign-in을 선택형으로 붙인다.
- 리스크:
  로그인 체계를 한 번에 바꾸면 사용자 세션 모델이 흔들릴 수 있다.
- 판단:
  "교체"보다 "병행 도입"이 맞다.

### 4.3 Qdrant

- GitHub: <https://github.com/qdrant/qdrant>
- 도입 목적:
  현재 검색 저장소를 production-friendly 한 벡터 DB로 강화한다.
- 현재 연결 지점:
  `biolinker/services/vector_store.py`
  `/match/rfp`, `/match/paper`, `/similar/profile`
- 기대 효과:
  payload 기반 필터링, dense+sparse hybrid search, 컬렉션 분리, 운영 확장성 확보
- 도입 방식:
  `VectorStore` 인터페이스를 유지한 채 어댑터를 추가한다.
  1차에서는 RFP 컬렉션만 Qdrant로 이동하고, 논문/자산은 순차 이전한다.
- 리스크:
  임베딩 전략이 불안정하면 DB를 바꿔도 결과가 좋아지지 않는다.
- 판단:
  GROBID 뒤에 붙여야 효과가 크다.

### 4.4 Prefect

- GitHub: <https://github.com/PrefectHQ/prefect>
- 도입 목적:
  공고 수집과 인덱싱을 앱 내부 스케줄러에서 운영 가능한 파이프라인으로 분리한다.
- 현재 연결 지점:
  `biolinker/services/scheduler.py`
  `kddf_crawler.py`
  `ntis_crawler.py`
  `vector_store.py`
- 기대 효과:
  retry, scheduling, observability, 수동 재실행, 실패 구간 재처리
- 도입 방식:
  현재 `collect_all_notices()` 흐름을 Prefect flow/task로 이관한다.
  앱은 수집 결과를 읽기만 하고, 수집 실행은 별도 worker가 담당하게 한다.
- 리스크:
  너무 빨리 도입하면 운영 도구만 늘고 제품 가치는 늦게 보일 수 있다.
- 판단:
  검색/파싱 개선 직후 운영 안정화 단계에서 도입

### 4.5 Snapshot

- GitHub:
  <https://github.com/snapshot-labs/snapshot-docs>
  <https://github.com/snapshot-labs/snapshot-hub>
- 도입 목적:
  Firestore 기반 임시 거버넌스를 신뢰 가능한 off-chain 투표 경험으로 업그레이드한다.
- 현재 연결 지점:
  `biolinker/routers/governance.py`
  프론트 proposal/vote 화면
- 기대 효과:
  가스리스 투표, 서명 검증, voting strategy 확장, DAO 브랜딩 강화
- 도입 방식:
  1차는 Snapshot space를 생성하고 프론트에서 proposal/vote 링크를 연결한다.
  2차에서 proposal mirror API나 Snapshot embed를 붙인다.
- 리스크:
  treasury execution은 별도 설계가 필요하다.
- 판단:
  제품의 DAO 성격을 강화할 시점에 도입

### 4.6 Dataverse

- GitHub: <https://github.com/IQSS/dataverse>
- 도입 목적:
  장기적으로 연구 데이터 저장소, DOI, 메타데이터, 보존, 리뷰 워크플로를 강화한다.
- 기대 효과:
  연구 저장소 신뢰도 확보, 장기 보존, 데이터 인용/발견성 개선
- 리스크:
  Java/Payara/Solr/Postgres 운영 부담이 크고, 현재 팀 규모 대비 무겁다.
- 판단:
  지금은 PoC만 검토하고 즉시 도입은 보류

## 5. 단계별 실행 계획

## Phase 1. 검색 품질과 지갑 UX 개선

기간: 2주

### Issue 1. Add GROBID as optional parser service

- Status:
  completed on 2026-03-20
- 목표:
  Docker Compose에 GROBID 컨테이너를 추가하고 헬스체크를 구성한다.
- 산출물:
  `docker-compose.yml` 업데이트
  `biolinker/services/grobid_parser.py`
  `.env.example`에 GROBID URL 추가
- 완료 조건:
  로컬에서 PDF 1개 업로드 시 GROBID 파싱 결과가 로그 또는 API 응답에 반영된다.

### Issue 2. Map structured paper metadata into vector indexing

- 목표:
  `title`, `abstract`, `authors`, `affiliations`, `references`, `doi`를 분리 저장한다.
- 산출물:
  `AssetManager`와 `VectorStore` 메타데이터 스키마 확장
- 완료 조건:
  업로드한 논문이 plain text가 아니라 구조화 필드와 함께 저장된다.

### Issue 3. Replace manual wallet connect flow with wagmi and RainbowKit

- 목표:
  프론트에서 직접 `window.ethereum`을 다루는 코드를 제거한다.
- 산출물:
  wallet provider 설정
  connect button 교체
  체인/계정 상태 훅 적용
- 완료 조건:
  MetaMask/Rabby 연결, 계정 변경, 네트워크 변경이 안정적으로 동작한다.

### Issue 4. Add SIWE-based wallet session endpoints

- 목표:
  `nonce`, `verify`, `session` API를 추가한다.
- 산출물:
  `biolinker/routers/auth_wallet.py` 또는 기존 auth 확장
- 완료 조건:
  서명 검증 후 wallet session을 서버에서 확인할 수 있다.

## Phase 2. 검색 엔진과 운영 파이프라인 개선

기간: 2~3주

### Issue 5. Introduce Qdrant adapter behind current VectorStore API

- 목표:
  현재 API를 깨지 않고 Qdrant를 연결한다.
- 산출물:
  `QdrantVectorStore` 어댑터
  환경변수 기반 저장소 선택
- 완료 조건:
  `/match/rfp`가 Qdrant 기반으로 동일 응답 형태를 반환한다.

### Issue 6. Add metadata filters and hybrid search

- 목표:
  `source`, `type`, `deadline`, `keywords`, `trl` 조건으로 필터 검색을 지원한다.
- 완료 조건:
  프론트에서 공고 소스별 필터와 검색 조합이 가능하다.

### Issue 7. Move notice collection pipeline to Prefect

- 목표:
  KDDF/NTIS 수집, 상세 fetch, 인덱싱을 Prefect flow로 전환한다.
- 완료 조건:
  실패한 작업을 UI 또는 CLI에서 재실행할 수 있다.

### Issue 8. Add pipeline monitoring and retry policy

- 목표:
  실패율과 마지막 성공 시각을 운영자가 확인할 수 있게 한다.
- 완료 조건:
  "마지막 수집 성공", "실패 건수", "재시도 결과"가 남는다.

## Phase 3. 거버넌스 강화

기간: 1~2주

### Issue 9. Launch Snapshot space for desci-platform

- 목표:
  실제 proposal/vote를 Snapshot space로 운영한다.
- 완료 조건:
  테스트 proposal 생성, 투표, 결과 확인이 가능하다.

### Issue 10. Mirror governance status into product UI

- 목표:
  제품 내 proposal 화면을 Snapshot 데이터와 연결한다.
- 완료 조건:
  기존 Firestore mock 대신 Snapshot 상태를 읽어 온다.

## Phase 4. 전략 검토 과제

기간: 별도 PoC

### Issue 11. Evaluate Dataverse as research repository backbone

- 목표:
  Dataverse를 메타데이터 저장소/출판 저장소로 쓸지 검토한다.
- 완료 조건:
  아래 항목에 대한 의사결정 메모가 나온다.
  DOI 발급 방식
  ORCID 연계
  IPFS/NFT와 역할 분담
  운영 비용
  마이그레이션 난이도

## 6. 권장 구현 순서

실행 순서는 아래가 가장 안전하다.

1. `GROBID`
2. `wagmi + RainbowKit`
3. `SIWE`
4. `Qdrant`
5. `Prefect`
6. `Snapshot`
7. `Dataverse` PoC

이 순서를 권장하는 이유는 아래와 같다.

- 먼저 업로드 데이터 품질을 높여야 검색 품질이 올라간다.
- 그 다음 사용자 체감이 큰 지갑 UX를 안정화해야 한다.
- 검색 엔진 교체는 데이터 품질 개선 뒤에 해야 효과가 크다.
- 운영 파이프라인 도입은 제품 기능이 어느 정도 안정된 뒤가 맞다.
- 거버넌스와 저장소 백본은 제품 포지셔닝이 더 분명해질 때 붙여도 늦지 않다.

## 7. 이번 스프린트에서 바로 할 일

- `Issue 1` GROBID 컨테이너 추가
- `Issue 2` 구조화 메타데이터 인덱싱
- `Issue 3` wagmi/RainbowKit 연결

위 3개만 완료해도 아래 변화가 바로 보인다.

- 논문 업로드 품질 향상
- 검색/매칭 신뢰도 개선
- 월렛 연결 UX 개선

## 8. 보류 또는 비권장 사항

- Firebase Auth를 즉시 제거하지 않는다.
- Dataverse를 지금 바로 core backend로 치환하지 않는다.
- Snapshot 도입 전에 on-chain governor로 바로 점프하지 않는다.
- Qdrant 도입 전에 임베딩 fallback 문제를 방치하지 않는다.

## 9. 성공 지표

- 업로드 논문의 구조화 메타데이터 추출 성공률 80% 이상
- `/match/rfp` 결과에 대한 내부 평가 만족도 향상
- 지갑 연결 실패율 감소
- 공고 수집 실패 건 재처리 시간 단축
- proposal/vote 플로우의 신뢰도 개선

## 10. 참고 GitHub 프로젝트

- GROBID: <https://github.com/grobidOrg/grobid>
- Qdrant: <https://github.com/qdrant/qdrant>
- wagmi: <https://github.com/wevm/wagmi>
- RainbowKit: <https://github.com/rainbow-me/rainbowkit>
- SIWE: <https://github.com/spruceid/siwe>
- Prefect: <https://github.com/PrefectHQ/prefect>
- Snapshot Docs: <https://github.com/snapshot-labs/snapshot-docs>
- Snapshot Hub: <https://github.com/snapshot-labs/snapshot-hub>
- Dataverse: <https://github.com/IQSS/dataverse>
