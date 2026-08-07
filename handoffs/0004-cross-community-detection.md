# 핸드오프 0004 — 교차 확산 감지 되살리기 (한국어 조사 정규화 + 클러스터 키 안정화)

- **상태:** DONE
- **기획자:** Claude
- **추천 실행자:** MiMo 또는 Codex (한국어 텍스트 처리)
- **실행자:** Codex
- **작성일:** 2026-08-06

## 목표

"여러 커뮤니티에서 동시에 뜬다"는 신호를 실제로 작동하게 만든다. 지금은 사실상 꺼져 있다.

## 배경

X 소재 판별에 가장 믿을 만한 신호가 교차 확산이다. 코드에도 배점이 있다 —
직접 항목 `cross_boost` 최대 15점, 애그리게이터 `cross_community` 최대 25점.
**그런데 거의 발화하지 않는다.**

원인 둘이 진단에서 확인됐다.

**1. 한국어 조사가 정규화되지 않는다.** `_community_titles_match`(`fast_viral_collector.py`)가
토큰 Jaccard 0.5를 요구하는데:

```
"편의점 알바가 진상 손님한테 한 말"  → {편의점, 알바가, 진상, 손님한테, ...}
"편의점 알바 진상 손님 응대 레전드"  → {편의점, 알바,  진상, 손님,   ...}
교집합 2 / 합집합 9 = 0.22  →  같은 사건인데 클러스터 안 됨
```

완전히 같은 제목으로 복붙된 짤에서만 발화한다.

**2. 클러스터 키가 불안정하다.** 트래커 키가 `community:cluster:{cluster_key}`인데
`cluster_key`는 **클러스터 대표(`cluster[0]`)의 제목 토큰 해시**다. 대표는 IssueLink
프론트페이지의 DOM 순서로 정해지는데, 그 순서는 계속 바뀐다. 키가 바뀌면 관측 히스토리가
끊기고 `previous_observed_at`이 None이 되어 신뢰도가 `low`(coverage 0.82)로 떨어지고
증가량 15점도 못 받는다.

**즉 두 번째 커뮤니티가 그 글을 받아 클러스터가 커지는 순간 — 확산이 시작됐다는 가장 좋은
신호가 나오는 그 순간 — 점수가 오히려 떨어질 수 있다.**

## 범위

- **건드릴 것:** `fast_viral_collector.py`의 `_community_titles_match`,
  `_annotate_community_clusters`, 클러스터 키 생성부, 대응 테스트.
- **건드리지 말 것:** 수집 대상, 제외 필터, 커널 판정, 화면 레이아웃, 점수 배점 자체.

## 단계

1. 제목 토큰화에 **한국어 조사·어미 정규화**를 넣는다. 형태소 분석기를 새로 설치하지 말고
   접미사 규칙으로 근사한다(`이·가·은·는·을·를·에·에서·한테·에게·으로·로·의·도·만` 등 절단).
   `~/Desktop/Joopark`에 Kiwi를 정확 버전으로 고정해 쓴 선례가 있지만, 여기서는 의존성을
   늘리지 않는 쪽을 우선한다.
2. 정규화 후 Jaccard 임계를 재조정한다. 0.5가 여전히 맞는지 실제 제목 쌍으로 확인한다.
3. **클러스터 키를 순서에 무관하게 만든다.** 대표 항목의 해시가 아니라 클러스터 전체에서
   안정적으로 도출되는 값을 쓴다(예: 구성원 토큰의 교집합, 또는 최소 `post_id`).
4. 같은 사건이 소스를 옮겨 다녀도 히스토리가 이어지는지 확인한다.

## 수용 게이트

- `.venv/bin/python -m pytest automation/getdaytrends/tests -q` → 기존 921 유지 + 신규 통과.
- **테스트로 증명할 것 세 가지:**
  ① 조사만 다른 같은 사건 제목 쌍이 매칭된다
  ② 무관한 제목 쌍은 여전히 매칭되지 않는다(과매칭 방지)
  ③ 클러스터 구성원 순서를 바꿔도 키가 같다
- 실제 레이더 응답에서 `cross_community_source_count`가 2 이상인 항목이 나오는지 확인하고
  건수를 반환 섹션에 적는다. 지금은 사실상 항상 1이다.

## 금지사항

- 형태소 분석기(konlpy·mecab 등) 신규 설치 금지. 표준 라이브러리와 기존 의존성으로 해결한다.
- 과매칭 주의 — 조사를 다 떼면 짧은 제목끼리 우연히 겹칠 수 있다. 반드시 반대 방향 테스트를 넣는다.
- 점수 배점을 손대지 않는다. 이 핸드오프는 "신호가 발화하게" 만드는 것이지 배점 조정이 아니다.
- 되돌릴 수 없는 외부 행위 금지.

## 반환 (실행자가 채운다)

- 결과: 한국어 조사 접미사를 의존성 없이 정규화하고 Jaccard 0.5를 유지했다. 입력 순서에 흔들리던 대표 글 기반 묶음을 제목 쌍의 연결 성분으로 바꾸고, 구성원 공통 토큰 기반 키로 안정화했다. 같은 사건/과매칭 방지/구성원 순서/커널 `signals`·`exposure_reasons` 보존 회귀 4종을 추가했다. 전체 테스트는 957 passed·7 skipped. 저장된 실제 레이더 응답 12건에 새 클러스터러를 적용했을 때 `cross_community_source_count >= 2`는 6건이었다.
- 실행한 명령: `git merge main --ff-only`; `.venv/bin/python -m pytest automation/getdaytrends/tests/test_fast_viral_collector.py automation/getdaytrends/tests/test_kernel_screen.py -q` (기준 69 passed); `.venv/bin/python -m pytest automation/getdaytrends/tests/test_fast_viral_collector.py automation/getdaytrends/tests/test_kernel_screen.py automation/getdaytrends/tests/test_og_enrich.py -q` (80 passed); `.venv/bin/python -m pytest automation/getdaytrends/tests -q` (957 passed·7 skipped); `curl -sS http://127.0.0.1:8010/api/fast-viral | PYTHONPATH=automation/getdaytrends .venv/bin/python ...` (실응답 재클러스터링 6건); `git diff --check`.
- 남은 것: 0004 범위에는 없음. 새 외부 refresh는 `STATE.md`에 별건으로 기록된 브라우저 위장 UA가 아직 남아 있어 실행하지 않았고, 이미 저장된 실제 API 응답만 읽어 검증했다.
