#!/bin/bash
# GitHub Issues 일괄 생성 스크립트
#
# 사용법:
#   chmod +x scripts/create_github_issues.sh
#   ./scripts/create_github_issues.sh
#
# 사전 준비:
#   gh auth login

set -e  # 에러 발생 시 중단

echo "=========================================="
echo "GitHub Issues 생성 시작"
echo "=========================================="
echo ""

# GitHub CLI 로그인 확인
if ! gh auth status >/dev/null 2>&1; then
    echo "❌ GitHub CLI 로그인이 필요합니다."
    echo "   다음 명령을 실행하세요: gh auth login"
    exit 1
fi

echo "✅ GitHub CLI 인증 확인 완료"
echo ""

# 저장소 확인
REPO="biojuho/BIOJUHO-Projects"
echo "📦 저장소: $REPO"
echo ""

# Issue 생성 카운터
CREATED=0
FAILED=0

# Critical Issues (2개, Issue #3은 이미 완료)
echo "[1/12] Creating Issue #1: GitHub Security Features..."
if gh issue create \
  --repo "$REPO" \
  --title "Enable GitHub Security Features" \
  --label "security,critical,devops" \
  --body-file ".github/ISSUE_TEMPLATES/01-github-security-features.md"; then
    ((CREATED++))
    echo "✅ Issue #1 생성 완료"
else
    ((FAILED++))
    echo "❌ Issue #1 생성 실패"
fi
echo ""

echo "[2/12] Creating Issue #2: Remove Gemini 2.0 Flash..."
if gh issue create \
  --repo "$REPO" \
  --title "Remove Deprecated Gemini 2.0 Flash Model" \
  --label "technical-debt,critical,backend" \
  --body-file ".github/ISSUE_TEMPLATES/02-remove-gemini-2-0-flash.md"; then
    ((CREATED++))
    echo "✅ Issue #2 생성 완료"
else
    ((FAILED++))
    echo "❌ Issue #2 생성 실패"
fi
echo ""

# High Priority Issues (3개)
echo "[3/12] Creating Issue #4: PostgreSQL Migration..."
if gh issue create \
  --repo "$REPO" \
  --title "Migrate AgriGuard Database to PostgreSQL" \
  --label "database,high,backend" \
  --body-file ".github/ISSUE_TEMPLATES/04-migrate-postgresql.md"; then
    ((CREATED++))
    echo "✅ Issue #4 생성 완료"
else
    ((FAILED++))
    echo "❌ Issue #4 생성 실패"
fi
echo ""

echo "[4/12] Creating Issue #5: Standardize Runtime Versions..."
if gh issue create \
  --repo "$REPO" \
  --title "Standardize Runtime Versions Across Projects" \
  --label "infrastructure,high,devops" \
  --body-file ".github/ISSUE_TEMPLATES/05-standardize-runtime-versions.md"; then
    ((CREATED++))
    echo "✅ Issue #5 생성 완료"
else
    ((FAILED++))
    echo "❌ Issue #5 생성 실패"
fi
echo ""

echo "[5/12] Creating Issue #6: Implement Batch API..."
if gh issue create \
  --repo "$REPO" \
  --title "Implement LLM Batch API for Cost Optimization" \
  --label "backend,high,optimization" \
  --body-file ".github/ISSUE_TEMPLATES/06-implement-batch-api.md"; then
    ((CREATED++))
    echo "✅ Issue #6 생성 완료"
else
    ((FAILED++))
    echo "❌ Issue #6 생성 실패"
fi
echo ""

# Medium Priority Issues (4개)
echo "[6/12] Creating Issue #7: CI/CD Pipeline..."
if gh issue create \
  --repo "$REPO" \
  --title "Implement CI/CD Pipeline with GitHub Actions" \
  --label "devops,medium,infrastructure" \
  --body-file ".github/ISSUE_TEMPLATES/07-cicd-pipeline.md"; then
    ((CREATED++))
    echo "✅ Issue #7 생성 완료"
else
    ((FAILED++))
    echo "❌ Issue #7 생성 실패"
fi
echo ""

echo "[7/12] Creating Issue #8: pytest Coverage..."
if gh issue create \
  --repo "$REPO" \
  --title "Improve pytest Coverage to 50%+" \
  --label "testing,medium,backend" \
  --body-file ".github/ISSUE_TEMPLATES/08-pytest-coverage.md"; then
    ((CREATED++))
    echo "✅ Issue #8 생성 완료"
else
    ((FAILED++))
    echo "❌ Issue #8 생성 실패"
fi
echo ""

echo "[8/12] Creating Issue #9: Qdrant POC..."
if gh issue create \
  --repo "$REPO" \
  --title "Evaluate Qdrant as ChromaDB Alternative" \
  --label "research,medium,backend" \
  --body-file ".github/ISSUE_TEMPLATES/09-qdrant-poc.md"; then
    ((CREATED++))
    echo "✅ Issue #9 생성 완료"
else
    ((FAILED++))
    echo "❌ Issue #9 생성 실패"
fi
echo ""

echo "[9/12] Creating Issue #10: Docker Compose Integration..."
if gh issue create \
  --repo "$REPO" \
  --title "Docker Compose Full Integration + Docs" \
  --label "devops,medium,documentation" \
  --body-file ".github/ISSUE_TEMPLATES/10-docker-compose-setup.md"; then
    ((CREATED++))
    echo "✅ Issue #10 생성 완료"
else
    ((FAILED++))
    echo "❌ Issue #10 생성 실패"
fi
echo ""

# Documentation Issues (2개)
echo "[10/12] Creating Issue #11: Update CLAUDE.md..."
if gh issue create \
  --repo "$REPO" \
  --title "Update CLAUDE.md with Latest Architecture" \
  --label "documentation" \
  --body-file ".github/ISSUE_TEMPLATES/11-update-claude-md.md"; then
    ((CREATED++))
    echo "✅ Issue #11 생성 완료"
else
    ((FAILED++))
    echo "❌ Issue #11 생성 실패"
fi
echo ""

echo "[11/12] Creating Issue #12: Team Onboarding Guide..."
if gh issue create \
  --repo "$REPO" \
  --title "Create Team Onboarding Guide" \
  --label "documentation" \
  --body-file ".github/ISSUE_TEMPLATES/12-team-onboarding-guide.md"; then
    ((CREATED++))
    echo "✅ Issue #12 생성 완료"
else
    ((FAILED++))
    echo "❌ Issue #12 생성 실패"
fi
echo ""

# Monitoring Issues (1개)
echo "[12/12] Creating Issue #13: Sentry Error Tracking..."
if gh issue create \
  --repo "$REPO" \
  --title "Implement Sentry Error Tracking" \
  --label "monitoring,medium,backend" \
  --body-file ".github/ISSUE_TEMPLATES/13-sentry-error-tracking.md"; then
    ((CREATED++))
    echo "✅ Issue #13 생성 완료"
else
    ((FAILED++))
    echo "❌ Issue #13 생성 실패"
fi
echo ""

# 결과 요약
echo "=========================================="
echo "생성 완료"
echo "=========================================="
echo "✅ 성공: $CREATED개"
echo "❌ 실패: $FAILED개"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 모든 Issues가 성공적으로 생성되었습니다!"
    echo ""
    echo "다음 단계:"
    echo "  1. GitHub 웹에서 Issues 확인: https://github.com/$REPO/issues"
    echo "  2. Critical Issues부터 작업 시작 (#1, #2)"
    echo "  3. Milestone 설정 (선택 사항)"
else
    echo "⚠️  일부 Issues 생성에 실패했습니다."
    echo "   실패한 Issues는 수동으로 생성하세요."
fi

echo ""
echo "📝 참고 문서: docs/GITHUB_ISSUES_CREATION_GUIDE.md"
