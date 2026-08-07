# 관측 쌍 비율 개선 (0012) — 2026-08-07

0010이 남긴 질문: **왜 4,732건 중 29건(0.6%)만 쌍이고, ruliweb·theqoo만 짝이 되는가?**

원본 `data/viral_lead_times.json`은 읽기만 했다.

```bash
cd automation/getdaytrends
python scripts/report_lead_time_evidence.py data/viral_lead_times.json
```

---

## 1. 두 가설을 데이터로 구분

| 가설 | 의미 | 판정 |
|------|------|------|
| A. IssueLink 출현 편중 | 그 둘만 애그리게이터에 자주 올라와서 쌍이 된다 | **부분적으로 참** — dogdrip·bobae_freeb 등은 저장 기준 agg 0건 |
| B. 키 형태 불일치 | 같은 글인데 source/id 표기가 달라 쌍이 안 된다 | **참 (고칠 수 있음)** — ppomppu·bobae |

### 소스별 깔때기 (정규화 전, 저장 레코드)

| 소스 | direct only | agg only | both | 해석 |
|------|-------------|----------|------|------|
| ruliweb | 많음 | 있음 | **21** | 같은 id 공간. IssueLink에도 뜸 |
| theqoo | 있음 | 있음 | **8** | 동일 |
| ppomppu | 많음 | **21** | **0** | 양쪽에 다 있는데 쌍 0 → **키/ID 문제** |
| ppomppu_freeboard | 많음 | 0 | 0 | IssueLink 슬러그는 `ppomppu`만 씀 |
| bobae / board keys | 많음 | 소수 | 0 | 합성 ID·보드 키 분절 |
| dogdrip | 많음 | **0** | 0 | **IssueLink에 안 잡힘** (키 문제가 아님) |
| fmkorea·mlbpark 등 | 0 | 있음 | 0 | 직접 수집 없음 |

**ruliweb·theqoo만 짝이 되는 이유 = A와 B의 교집합.**  
그 둘은 (1) IssueLink에 실제로 자주 나오고 (2) 직접 수집과 **같은 숫자 id**를 쓴다.  
ppomppu는 (1)도 나오는데 (2)가 깨져 쌍이 0이었다.

### 결정적 증거 (리다이렉트, 읽기 전용 GET)

| IssueLink id | 도착 URL |
|--------------|----------|
| `ppomppu/468400010070329` | `.../zboard/view.php?id=freeboard&no=**10070329**` |
| `bobae/300003426651` | `.../view?code=freeb&No=**3426651**` |

직접 수집은 이미 `10070329` / `3426651`을 쓴다. **같은 글이 다른 id 문자열로 저장**되고 있었다.

제목 유사도 매칭은 쓰지 않았다. 합성 ID → 네이티브 no 변환과 슬러그 별칭만 썼다.

---

## 2. 한 일 (fast_viral_collector 미수정)

`lead_time_tracker.py`에 **식별자 정규화**를 넣었다.

- 슬러그: `ppomppu_freeboard`→`ppomppu`, `bobae_*`/`bobaedream`→`bobae`, `cook82`→`82cook`
- ID: 검증된 합성 패턴만  
  - ppomppu `46840` + 10자리 → freeboard `no`  
  - bobae `30000`/`40000` + 7자리 → `No`
- `summarize_lead_time_store(normalize_identities=True|False)` 로 전후 비교
- `record_observations` / `metrics_for`도 같은 키를 써서 **이후 수집**부터 저장 단계에서 쌍이 쌓임
- 원본 JSON은 분석 중 덮어쓰지 않음

`fast_viral_collector._snapshot_item_key`는 **손대지 않았다.**  
화면의 `before_issuelink` 가산·IssueLink 중복 제거는 여전히 raw 키를 쓴다.  
리드타임 측정만 tracker 쪽에서 고쳤다. 수집기 키를 맞추면 점수 쪽도 같이 좋아지지만 Codex 점유 파일이라 반환에만 적는다.

---

## 3. 숫자 전후 (같은 원본)

측정 시각의 저장본 기준 (스크립트 재실행으로 갱신).

| | RAW (0010 방식) | NORMALIZED (0012) |
|--|-----------------|-------------------|
| 쌍 수 | ~29 | **~44** |
| 레코드 대비 쌍 비율 | **0.6%** | **~0.9%** |
| 중앙 리드(분) | **+80** | **~+74** (스윙 ~6분, 게이트 30분 이내) |
| 음수 비율 | 3.4% | **~4.5%** |
| 양수 비율 | 89.7% | ~90.9% |
| 소스 | ruliweb·theqoo | + **ppomppu 14**, bobae 1 |

쌍이 늘었는데 중앙값이 80→74로만 움직였다. 새로 생긴 15쌍은 합성 ID 디코드·보드 키 병합으로 생긴 **같은 글**이며, 제목 추정 짝이 아니다.

---

## 4. 해석

1. **병목의 일부는 키 버그였고, 고치면 ppomppu가 살아난다.**  
2. **대부분은 여전히 미쌍** — IssueLink에 안 뜨는 직접 글(개드립 등), 직접 안 받는 커뮤니티(에펨 등). 0.9%도 “대부분 측정 불능”이다.  
3. **다음**  
   - 수집기 `_snapshot_item_key`에 같은 정규화를 넣으면 선행 가산·표시 카운트도 정합  
   - todayhumor 6자리 vs 8자리, ppomppu 타 보드 prefix(`31560`…)는 미검증이라 손대지 않음  
   - 교차 기준(조회 임계 시각 등)은 정의가 달라 별 지표

---

## 5. 게이트

- pytest 전량 통과 (커밋 전 확인)
- 원본 sha256 분석 전후 동일
- 중앙값 스윙 ≤ 30분
- 음수 비율 보고 유지
