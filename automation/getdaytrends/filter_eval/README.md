# filter_eval — 필터가 얼마나 놓치는지 재는 자 (핸드오프 0033)

정치 소재 제외 필터(`content_filters.py`의 `excluded_topic_reason`)가
**얼마나 놓치고 얼마나 잘못 막는지를 숫자로 말하기 위한** 평가셋과 측정 루프다.

지금은 "안민석·선관위·당진시의회가 통과한다"는 것만 알고, **얼마나 뚫리는지는 모른다.**
사전(단어 목록)을 더 늘리기 전에 자를 먼저 만든다. 에이전트가 보고한 수치는 기획자가
재현한 뒤에 쓴다 — 이 도구는 그 재현의 자다.

## 무엇을 재는가

정치 축 **하나만** 잰다. 다른 버킷(스포츠·증시·부동산·성별 갈등·애니·핫딜)은 대상이 아니다.
필터가 정치를 놓치는가(위음성), 비정치를 잘못 막는가(위양성)를 잰다.

## 파일

| 파일 | 역할 |
| --- | --- |
| `build_eval_set.py` | 읽기 전용 GET 으로 `/api/fast-viral`, `/api/x-radar` 에서 표본을 뽑아 `eval-set.tsv`에 누적 |
| `eval_filter.py` | `eval-set.tsv`에서 라벨이 채워진 행만으로 혼동행렬·재현율·정밀도·놓침 목록을 낸다 |
| `eval-set.tsv` | 라벨링 대상. `label` 열은 사람이 채운다 |

## 평가셋 형식 — `eval-set.tsv`

```
id  source  title  extra_text  filter_verdict  filter_reason  label  labeled_by  labeled_at
```

- `title` — fast-viral은 글 제목, x-radar는 검색어 키워드.
- `extra_text` — x-radar의 딸린 뉴스 원문 제목을 공백으로 이어 붙인 것. fast-viral은 빈칸.
- `filter_verdict` — 지금 필터의 판정(`allow`/`block`). `(title, extra_text)`에 대해
  `excluded_topic_reason`을 부른 결과다. TSV의 보이는 두 열로 재현 가능하다.
- `filter_reason` — `excluded_topic_reason()`의 사유 문자열(없으면 빈칸).
- **`label` — 사람이 채운다. 값은 `politics` / `not_politics` / `unclear` 셋 중 하나.**
- `labeled_by` / `labeled_at` — 라벨러 이름과 시각.

## 절대 지키는 규칙

- **`label` 열을 스크립트/휴리스틱으로 채우지 않는다.** 필터가 필터를 채점하면 순환이 되어
  이 평가 전체가 무의미해진다. 라벨은 사람이 판단해 넣는다.
- `build_eval_set.py`는 새 파일만 다룬다. 기존 코드(특히 `content_filters.py`)는 고치지 않는다.

## 사용법

```bash
# 1. 표본을 뽑아 누적한다 (반복 실행 — 같은 id는 한 번만 들어간다)
python3 filter_eval/build_eval_set.py

# 2. 라벨을 사람이 채운다 (eval-set.tsv 의 label 열을 직접 편집)

# 3. 잰다
python3 filter_eval/eval_filter.py
python3 filter_eval/eval_filter.py --json
```

`build_eval_set.py`는 며칠 돌리면 표본이 쌓이도록 설계했다. 서버가 꺼져 있어도 죽지 않고
기존 행만 유지한다. `/refresh` 계열 API는 부르지 않는다(수집을 유발).

## 측정 정의

라벨이 채워진 행만 쓴다(`unclear`는 분모에서 빼고 따로 센다).

| | filter=block | filter=allow |
| --- | --- | --- |
| label=politics | TP (맞게 막음) | **FN (놓침)** |
| label=not_politics | **FP (잘못 막음)** | TN (맞게 허락) |

- **재현율(recall)** = TP ÷ (TP+FN) — 낮을수록 정치를 많이 놓친다.
- **정밀도(precision)** = TP ÷ (TP+FP) — 낮을수록 비정치를 과잉 차단한다.
- **놓친 항목 목록**(FN)이 사전 확장의 입력이 된다.

**표본이 30건 미만이면 비율을 내지 않고 `n<30`으로 표시한다.** 희소 칸의 비율으로
결론을 낸 실패가 이 프로젝트에 여러 번 있었다.

## 한계 — 반드시 알아야 할 것

1. **표본은 이미 업스트림 게이트를 통과해 화면에 뜬 것들이다.** 수집 단계에서 걸러진
   항목은 이 표본에 보이지 않는다. 그래서 **재현율이 실제보다 좋게(높게) 나올 수 있다.**

2. **걸러진(차단) 항목을 표본에 넣을 수 없다.** 두 API 모두 통과한 항목만 `items`에 담고,
   차단분은 `excluded_topic_counts`/`filter_summary`의 **집계 카운트로만** 노출한다(제목 없음).
   디스크의 관측 파일에도 차단 후보의 제목은 남지 않는다. 제목 단위의 차단 항목을 얻으려면
   콜렉터를 고치거나 `/refresh`를 불러야 하는데, 둘 다 이 발주의 금지 범위다.
   **결과적으로 과잉 차단(FP·정밀도)은 이 측정만으로는 잴 수 없다.** 이 도구가 민감하게
   잡을 수 있는 것은 '놓친 정치(FN)'뿐이다.

3. **라벨이 한 사람 판단이면 신뢰도를 모른다.** 2인 이상이 라벨링하면 일치율(예: Cohen's κ)을
   함께 내야 한다. 지금은 일치율 산출까지는 구현하지 않았다.

4. **`filter_verdict`는 행이 처음 추가될 때의 필터 상태를 기록한다.** `content_filters.py`가
   바뀌면 과거 행의 판정과 어긋날 수 있다. 기존 행은 재실행해도 갱신하지 않는다(라벨 보존).

## 무엇을 결론짓지 않는가

라벨이 없으면 아직 아무것도 모른다. 이 도구는 숫자를 낼 뿐, 필터가 좋다/나쁘다를 말하지 않는다.
