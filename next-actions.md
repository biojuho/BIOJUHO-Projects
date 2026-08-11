# Next Actions

> 세션 종료 시 `/session-workflow`가 이 파일의 갱신을 제안합니다.
> 2026-05-07 기준 — 시스템 고도화 세션

## Backlog (미완료)

- [ ] **[safe_auto] 0035 09시 첫 수집 검증** — `GET /api/collection-scheduler`의 두 레인 호출·오류 0, `/api/fast-viral`·`/api/x-radar` 회복, `data/filter_eval_shadow.sqlite3` 생성·정책 지문·allow/block 건수를 읽기 전용으로 확인. `/refresh` 직접 호출 금지.
- [ ] **[needs_human] 0033 평가셋 라벨** — `filter_eval/eval-set.tsv` 35행에 `politics/not_politics/unclear`, `labeled_by`, `labeled_at`을 사람이 기록한 뒤 `eval_filter.py` 실행. 기존 평가셋과 shadow 표본은 합치지 않음.
- [ ] **새 CI 게이트 첫 PR 실기동 확인** — GitHub Actions 실제 PR run URL이 생기면 merge 차단 동작 최종 확인
- [ ] **X 수동 발행**: Economy_Global 최종 문안 + posting 이미지 → X 게시 후 URL 기록
- [ ] **Canva token 브라우저 재인증** (PKCE flow): `canva_auth_server.py` 실행 → 토큰 갱신

## 다음 세션 복붙 메모

```text
시스템 고도화 완료 후 진행:
- CIE main.py 인코딩 복원 완료 (UTF-8)
- 레거시 파일 13개 삭제 완료
- HANDOFF/CONTEXT/next-actions 문서 리셋 완료
- CI security-quality-gate PR 코멘트 자동 리포팅 추가 완료
- 스모크 테스트 안정화 완료
- 미커밋 변경사항 정리 커밋 완료
```
