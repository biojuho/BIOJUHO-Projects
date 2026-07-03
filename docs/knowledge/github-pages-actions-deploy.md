# GitHub Pages를 Actions로 배포하기 — 전체 흐름과 함정

- 작성일: 2026-06-11
- 분류: 프로젝트 운영 지식
- 요약: GitHub Pages는 "브랜치에서 배포"와 "GitHub Actions로 배포" 두 모드가 있고, 우리는 Actions 모드(빌드 → 아티팩트 업로드 → 배포 3단계)를 쓴다. 가장 흔한 함정은 워크플로 파일을 로컬에서만 고치고 기본 브랜치에 푸시하지 않아 수동 실행(workflow_dispatch)이 아예 불가능한 상태 — 지금 우리가 정확히 그 상태다.

## 왜 우리에게 필요한가

JooPark Workspace는 빌드 단계 없는 정적 SPA지만, 모노레포(biojuho/BIOJUHO-Projects)의 하위 산출물(`dist/release`)만 골라 배포해야 해서 브랜치 모드 대신 Actions 모드가 필요하다. 로컬 `.github/workflows/joopark-pages.yml`은 템플릿(`docs/github-pages-workflow.yml`)과 일치하지만 **아직 커밋·푸시되지 않았다** — 점검 스크립트가 `remoteWorkflowFilesReady=false`를 내는 진짜 원인이 이것이다. 또 우리 리모트 이름은 `origin`이 아니라 `biojuho-projects`라서, origin을 가정한 명령은 그대로 실패한다. 첫 배포 전에 전체 흐름과 규칙을 정리해 둔다.

## 핵심 지식

### 공식 배포 흐름: 액션 3개, 잡 2개

공식 플로우는 build 잡과 deploy 잡으로 나뉜다([GitHub Docs: Using custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)).

1. **actions/configure-pages** — Pages를 활성화하고 사이트 메타데이터(URL 등)를 수집.
2. **actions/upload-pages-artifact** — 배포할 폴더를 "아티팩트"(워크플로가 만든 결과물 묶음)로 업로드. 형식은 단일 gzip tar 하나여야 하고, 심볼릭 링크 불가, 권장 1GB·최대 10GB 제한([upload-pages-artifact README](https://github.com/actions/upload-pages-artifact)).
3. **actions/deploy-pages** — 그 아티팩트를 실제 사이트로 배포.

공식 문서 예시 버전(2026-06-11 기준)은 `configure-pages@v5`, `upload-pages-artifact@v4`, `deploy-pages@v4`로, **우리 로컬 워크플로와 동일**하다. 각 저장소에는 더 새 메이저(configure-pages v6.0.0, deploy-pages v5.0.0 — 2026-03-25 릴리스, upload-pages-artifact v5.0.0 — 2026-04-10 릴리스)도 있으나, deploy-pages README는 여전히 `@v4`를 예시로 쓴다([deploy-pages README](https://github.com/actions/deploy-pages)). 첫 배포는 문서 예시 버전으로 가고, 메이저 업그레이드는 별도 작업으로 미루는 게 안전하다.

### 필요한 permissions 세 가지

permissions는 "이 워크플로가 저장소에서 뭘 할 수 있는지" 선언하는 권한 목록이다. Pages 배포에는 `contents: read`(코드 읽기), `pages: write`(Pages에 쓰기), `id-token: write`가 필요하다([GitHub Docs](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)). `id-token: write`는 OIDC 토큰(이 배포가 정당한 워크플로에서 나왔음을 증명하는 1회용 신분증)을 발급받기 위한 것으로, 어떤 브랜치에서 배포됐는지 검증해 무단 배포를 막는다([deploy-pages README](https://github.com/actions/deploy-pages)). 우리 워크플로에는 릴리스 증명(actions/attest@v4)용 `attestations: write`가 하나 더 있다. deploy 잡에는 `needs: build`와 `environment: github-pages`가 필수 — `needs`를 빼면 deploy가 아직 없는 아티팩트를 찾다 실패할 수 있다.

### workflow_dispatch: 수동 실행의 전제 조건

workflow_dispatch는 워크플로를 버튼(또는 명령)으로 수동 실행하는 트리거다. 핵심 규칙: **"이 이벤트는 워크플로 파일이 기본 브랜치(default branch)에 존재할 때만 실행을 트리거한다"**([GitHub Docs: Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)). 즉 로컬에만 있는 워크플로는 절대 수동 실행할 수 없다. 실행은 `gh workflow run <파일명> [--ref 브랜치] [-f 입력=값]` 형태로 한다([gh workflow run 매뉴얼](https://cli.github.com/manual/gh_workflow_run)).

### gh CLI의 workflow scope가 필요한 이유

scope는 gh 로그인 토큰에 붙는 권한 딱지다. `workflow` scope는 "GitHub Actions 워크플로 파일을 추가·수정할 수 있는 능력"을 부여한다([GitHub Docs: OAuth scopes](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps)). 이 scope 없이 `.github/workflows/` 안의 파일을 푸시하면 거부된다(동일 내용 파일이 이미 다른 브랜치에 있는 예외만 통과). 우리 gh 인증에는 이미 workflow scope가 있으므로 푸시 가능하다.

### 모노레포 하위 폴더만 배포하기

`upload-pages-artifact`의 `path` 입력(기본값 `_site/`)에 원하는 폴더를 지정하면 그 폴더만 사이트가 된다([upload-pages-artifact README](https://github.com/actions/upload-pages-artifact)). 우리는 `path: dist/release` — 모노레포 전체가 아니라 패키징 산출물만 올라간다. 주의: 이 액션은 **숨김 파일(`.`으로 시작)을 기본 제외**한다(`include-hidden-files: true`로 포함 가능, 단 `.git`·`.github`은 항상 제외).

### .nojekyll — Actions 모드에서는 불필요

브랜치 모드에서는 GitHub가 Jekyll(루비 기반 사이트 생성기)을 자동으로 돌리며, Jekyll은 `_`, `.`, `#`으로 시작하는 파일을 빌드에서 빼버린다([GitHub Docs: About GitHub Pages and Jekyll](https://docs.github.com/en/pages/setting-up-a-github-pages-site-with-jekyll/about-github-pages-and-jekyll)). 이를 막으려면 루트에 빈 `.nojekyll` 파일을 둬서 빌드를 건너뛰게 한다([GitHub Docs: Configuring a publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)). 반면 **Actions 모드는 아티팩트를 그대로 배포할 뿐 Jekyll을 돌리지 않으므로 `.nojekyll`이 필요 없다.** 우리 산출물에는 `_`로 시작하는 파일도 없다.

### 소스 모드: branch vs Actions

저장소 Settings → Pages → "Build and deployment" → Source에서 "Deploy from a branch"와 "GitHub Actions" 중 하나를 고른다([GitHub Docs](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)). Actions 모드여야 deploy-pages가 정상 동작한다. 우리 워크플로는 `configure-pages`에 `enablement: true`를 줘서 첫 실행 때 Pages 활성화를 시도한다(실제 동작은 첫 실행에서 확인 필요).

## 우리 프로젝트에 적용하기

현재 상태: 로컬 워크플로 파일 수정됨(미커밋), 리모트 이름 `biojuho-projects`, 첫 배포 전.

1. **커밋** — 워크플로와 템플릿을 함께:
   `git add .github/workflows/joopark-pages.yml docs/github-pages-workflow.yml`
   `git commit -m "Publish JooPark Pages workflow"`
2. **푸시** — 리모트 이름 주의(`origin` 아님). workflow_dispatch가 작동하려면 이 파일이 **저장소 기본 브랜치**에 도달해야 한다:
   `git push biojuho-projects HEAD` (현재 브랜치가 기본 브랜치가 아니면 main으로의 병합/브리지가 추가로 필요 — `scripts/plan-main-bridge.mjs` 참고)
3. **원격 검증 재실행** — `remoteWorkflowFilesReady`가 true로 바뀌는지 확인:
   `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write`
4. **(미설정 시) Pages 소스 확인** — 저장소 Settings → Pages → Source = "GitHub Actions". `enablement: true`가 처리해 줄 수도 있으나 첫 실행에서 확인.
5. **수동 실행**:
   `gh workflow run joopark-pages.yml -R biojuho/BIOJUHO-Projects -f ref=codex/joopark-workspace-release`
   실행 후 `gh run watch -R biojuho/BIOJUHO-Projects`로 진행 확인. deploy 잡 출력의 `page_url`이 사이트 주소다.

## 주의사항 / 흔한 실수

- **로컬 수정 후 커밋·푸시 누락**: workflow_dispatch는 기본 브랜치의 파일 기준이므로, 푸시 전에는 `gh workflow run`이 실패하거나 옛 버전이 실행된다. 지금 우리 `remoteWorkflowFilesReady=false`의 원인.
- **리모트 이름 가정**: 우리 리모트는 `biojuho-projects`다. `git push origin ...`을 쓰는 스크립트·습관은 그대로 실패한다.
- **deploy 잡에 `needs: build` 누락**: 두 잡이 동시에 돌아 deploy가 존재하지 않는 아티팩트를 찾다 실패할 수 있다.
- **permissions 누락**: `id-token: write`가 빠지면 deploy-pages가 OIDC 토큰을 못 받아 배포 거부된다.
- **Pages 소스가 branch 모드인 채 Actions 배포 시도**: Settings에서 Source를 "GitHub Actions"로 바꾸지 않으면 충돌한다. `enablement: true`의 실제 동작은 첫 실행에서 확인 필요.
- **숨김 파일 기대**: upload-pages-artifact는 `.`으로 시작하는 파일을 기본 제외한다. 산출물에 숨김 파일이 필요하면 `include-hidden-files: true`를 명시해야 한다(`.nojekyll`은 Actions 모드에선 애초에 불필요).

## 출처

모두 2026-06-11 접근.

- [GitHub Docs — Using custom workflows with GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [actions/deploy-pages README](https://github.com/actions/deploy-pages)
- [actions/upload-pages-artifact README](https://github.com/actions/upload-pages-artifact)
- [actions/configure-pages README](https://github.com/actions/configure-pages)
- [GitHub Docs — Manually running a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
- [GitHub Docs — Events that trigger workflows (workflow_dispatch)](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [gh CLI — gh workflow run](https://cli.github.com/manual/gh_workflow_run)
- [GitHub Docs — Scopes for OAuth apps (workflow scope)](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps)
- [GitHub Docs — Configuring a publishing source for your GitHub Pages site](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
- [GitHub Docs — About GitHub Pages and Jekyll](https://docs.github.com/en/pages/setting-up-a-github-pages-site-with-jekyll/about-github-pages-and-jekyll)
