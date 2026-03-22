# Enable GitHub Security Features

**Labels**: `security`, `critical`, `devops`
**Priority**: 🚨 **Critical** - 이번 주 완료 필수

---

## Description

GitHub의 기본 보안 기능을 활성화하여 시크릿 노출 및 의존성 취약점을 자동 감지합니다.

---

## Tasks

- [ ] GitHub Secret Scanning 활성화
- [ ] Push Protection 활성화 (시크릿 푸시 차단)
- [ ] Dependabot alerts 활성화
- [ ] Dependabot security updates 활성화
- [ ] Dependency Review 활성화 (PR 체크)
- [ ] CodeQL 정적 분석 설정 (Python, JavaScript, TypeScript)

---

## Acceptance Criteria

- ✅ Secret scanning이 활성화되어 기존 히스토리 스캔 완료
- ✅ 새로운 시크릿 푸시 시 자동 차단 확인
- ✅ Dependabot이 주간 업데이트 PR 생성 확인
- ✅ CodeQL이 PR마다 실행되어 결과 리포트 확인

---

## References

- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
- [Push Protection](https://docs.github.com/en/code-security/secret-scanning/push-protection-for-repositories-and-organizations)
- `docs/GITHUB_SECURITY_SETUP.md`

---

## 설정 가이드

### 1. Secret Scanning + Push Protection
**URL**: https://github.com/biojuho/BIOJUHO-Projects/settings/security_analysis

1. "Secret scanning" 섹션에서 **Enable** 클릭
2. "Push protection" 섹션에서 **Enable** 클릭

### 2. CodeQL 첫 실행
**URL**: https://github.com/biojuho/BIOJUHO-Projects/actions/workflows/codeql.yml

1. Actions 탭 → "CodeQL" 워크플로우 선택
2. "Run workflow" 버튼 클릭
3. 분석 완료 후 Security 탭에서 결과 확인

### 3. Branch Protection Rules
**URL**: https://github.com/biojuho/BIOJUHO-Projects/settings/branches

1. "Add branch protection rule" 클릭
2. Branch name pattern: `main`
3. 체크 항목:
   - ✅ Require a pull request before merging (1 approval)
   - ✅ Require status checks to pass before merging
   - ✅ Require conversation resolution before merging

---

**Estimated Time**: 5-10분
