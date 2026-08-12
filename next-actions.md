# Next Actions

> 세션 종료 시 `/session-workflow`가 이 파일의 갱신을 제안합니다.
> 2026-05-07 기준 — 시스템 고도화 세션

## Backlog (미완료)

- [ ] **[safe_auto] 0035 런타임 데이터 영속성 보강안 발주** — gitignore 대상 shadow SQLite·제목 메타가 워크트리 제거와 함께 소실됐다. 기존 파일 복구를 가장하지 말고 외부 데이터 경로·백업·복원 게이트를 별도 핸드오프로 설계한 뒤 구현. 09:40 이후 새 관측과 06:46~07:20 집계 기록은 합치지 않음.
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
