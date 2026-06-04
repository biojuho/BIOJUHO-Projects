# Vendored Open-Source Libraries

이 디렉터리의 파일들은 빌드/패키지 매니저 없이 정적으로 동작하도록 외부 OSS를
**원본 그대로(수정 없이) 로컬 동봉**한 것입니다. 모두 단일 파일 UMD 빌드이며,
`index.html`에서 `<script>`로 로드되어 각각 전역(`window.Fuse`, `window.marked`,
`window.DOMPurify`)을 노출합니다.

| 파일 | 라이브러리 | 버전 | 라이선스 | 출처 |
| --- | --- | --- | --- | --- |
| `fuse.min.js` | Fuse.js | 6.6.2 | Apache-2.0 | https://cdn.jsdelivr.net/npm/fuse.js@6.6.2/dist/fuse.min.js |
| `marked.umd.js` | marked | 18.0.4 | MIT | https://cdn.jsdelivr.net/npm/marked@18.0.4/lib/marked.umd.js |
| `purify.min.js` | DOMPurify | 3.4.7 | Apache-2.0 / MPL-2.0 | https://cdn.jsdelivr.net/npm/dompurify@3.4.7/dist/purify.min.js |

## 용도
- **Fuse.js** — 명령 팔레트(⌘K)의 퍼지(오타 허용)·관련도 랭킹 통합 검색.
- **marked** — 메모 본문 Markdown → HTML 렌더.
- **DOMPurify** — marked 출력 HTML의 XSS 소독(반드시 `marked.parse()` 결과를 소독한 뒤 렌더).

## 버전 고정 / 갱신
버전은 위 표의 URL로 고정되어 있습니다. 갱신 시 동일 URL 패턴에서 새 버전을 받아
파일을 교체하고, 이 표의 버전·라이선스를 갱신하세요. 각 파일 상단에는 원본
라이선스 헤더 주석이 보존되어 있습니다.

> Fuse.js는 7.x부터 UMD(전역) 빌드를 제공하지 않아(ESM/CJS만), 클래식 `<script>`
> ·무빌드 환경과 호환되는 마지막 UMD 라인인 **6.6.2**로 고정했습니다.
